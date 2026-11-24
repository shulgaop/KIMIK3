#!/usr/bin/env python3
"""budget.py — бюджет поездки кодом (обобщение budget.py проекта Япония).

Вход — бюджет.json:
[
  {"item": "Ж/д Токио → Танабэ", "amount": 14500, "currency": "JPY",
   "per_person": true, "note": "проверить расписание 2027"},
  {"item": "Отель", "amount": 80, "currency": "EUR", "per_day": 5}
]
Поля: amount в валюте currency; per_person — умножить на --members;
per_day — умножить на число дней; note — пометка «проверить».
Строки без amount (None) не считаются и помечаются — никаких чисел «из головы».

Конвертация в базовую валюту (--base, по умолчанию EUR) — живой курс
open.er-api.com через currency.py (тот же каталог scripts/).

Выдача: Бюджет.md (таблица + итоги) + JSON в stdout.

Использование:
  python3 budget.py бюджет.json --members 2 --days 8 --base EUR --out Бюджет.md
"""
import argparse, importlib.util, json, sys
from pathlib import Path


def load_currency_module():
    spec = importlib.util.spec_from_file_location(
        "currency", Path(__file__).parent / "currency.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def compute(items, members, days, base):
    """Итоги по валютам + конвертация в базовую по живому курсу."""
    rows, totals = [], {}
    for it in items:
        amt = it.get("amount")
        if amt is None:
            rows.append({**it, "total": None})
            continue
        n = 1
        if it.get("per_person"):
            n *= members
        if it.get("per_day"):
            n *= (it["per_day"] if isinstance(it["per_day"], int) else days)
        total = round(amt * n, 2)
        rows.append({**it, "total": total})
        cur = it.get("currency", base)
        totals[cur] = round(totals.get(cur, 0) + total, 2)

    converted, rate_note = None, ""
    others = [c for c in totals if c != base]
    if others:
        cur_mod = load_currency_module()
        rates = cur_mod.fetch_rates(base)["rates"]  # 1 base = X валюты
        converted = totals.get(base, 0) + sum(v / rates[c] for c, v in totals.items()
                                              if c != base and c in rates)
        missing = [c for c in others if c not in rates]
        if missing:
            rate_note = f"⚠️ нет курса для {missing}"
        converted = round(converted, 2)
    return rows, totals, converted, rate_note


def to_markdown(rows, totals, base, converted, rate_note, members, days):
    L = [f"# Бюджет поездки (на {members} чел., {days} дней)", ""]
    L += ["| Статья | Цена | Валюта | Итого | Примечание |", "|---|---|---|---|---|"]
    for r in rows:
        tot = f"{r['total']:.0f}" if r.get("total") is not None else "—"
        note = (r.get("note") or "")
        if r.get("total") is None:
            note = (note + "; " if note else "") + "⚠️ цены нет — не считается"
        mult = []
        if r.get("per_person"):
            mult.append(f"×{members} чел.")
        if r.get("per_day"):
            mult.append("×дни")
        L.append(f"| {r['item']} | {r.get('amount', '—')} | {r.get('currency', base)} | "
                 f"{tot} | {' '.join(mult)} {note} |")
    L += ["", "## Итоги (посчитаны скриптом)", ""]
    for c, v in totals.items():
        L.append(f"- **{c}: {v:,.0f}**".replace(",", " "))
    if converted is not None:
        L.append(f"- Итого в {base} (живой курс open.er-api.com): **{converted:,.0f}**"
                 .replace(",", " "))
    if rate_note:
        L.append(f"\n{rate_note}")
    return "\n".join(L)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("budget", help="бюджет.json — статьи расходов")
    ap.add_argument("--members", type=int, default=1)
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--base", default="EUR", help="базовая валюта итога")
    ap.add_argument("--out", help="куда записать Бюджет.md")
    args = ap.parse_args()

    items = json.load(open(args.budget, encoding="utf-8"))
    rows, totals, converted, rate_note = compute(items, args.members, args.days, args.base)
    md = to_markdown(rows, totals, args.base, converted, rate_note, args.members, args.days)
    if args.out:
        Path(args.out).write_text(md + "\n", encoding="utf-8")
    json.dump({"totals": totals, "total_in_base": converted, "base": args.base},
              sys.stdout, ensure_ascii=False, indent=2)
    print(f"\n✓ {len(items)} статей; итоги: " +
          ", ".join(f"{v:,.0f} {c}" for c, v in totals.items()), file=sys.stderr)


if __name__ == "__main__":
    main()
