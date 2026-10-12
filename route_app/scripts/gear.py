#!/usr/bin/env python3
"""gear.py — весовой чеклист снаряжения по методике LighterPack (F12).

Вход — gear.json (машиночитаемый список):
[
  {"category": "Сон", "item": "Спальник", "model": "Nordway −10", "weight_g": 1450,
   "qty": 1, "worn": false, "consumable": false, "shared": false},
  ...
]
- weight_g — в граммах; неизвестный — null (попадёт в итог как 0 и в список
  «взвесить» с пометкой ~);
- worn: true — на человеке (не входит в вес рюкзака);
- consumable: true — расходник (еда, вода, газ);
- shared: true — групповое: вес делится на число участников (--members).

Итоги считаются ТОЛЬКО здесь (не в уме, не LLM):
  Base = всё в рюкзаке без расходников; Worn = на себе;
  Consumables = еда+вода+газ; Total Pack = Base + Consumables;
  Skin-out = Total + Worn. Подитоги по категориям.

Выдача: Снаряжение.md (таблица по категориям + итоги; ★ — позиции с пометкой
дешёвой экономии веса) + gear_итоги.json. Контрольные ориентиры Base:
лёгкий горный поход 7–9 кг, комфортный 10–12, с зимней автономией 12–15.

Использование:
  python3 gear.py gear.json --members 2 --out Снаряжение.md
"""
import argparse, json, sys
from pathlib import Path

ORIENTERS = [(9, "лёгкий горный поход"), (12, "комфортный поход"),
             (15, "поход с зимней автономией"), (1e9, "тяжелее эталонов — пересмотреть!")]


def load_items(path):
    items = json.load(open(path, encoding="utf-8"))
    for i, it in enumerate(items):
        if not it.get("item"):
            sys.exit(f"Позиция {i + 1}: нет item")
        if it.get("weight_g") is None:
            it["weight_unknown"] = True
            it["weight_g"] = 0
    return items


def totals(items, members):
    """Итоги LighterPack. Всё в граммах; shared делится на членов команды."""
    def eff(it):
        w = (it.get("weight_g") or 0) * (it.get("qty") or 1)
        return w / members if it.get("shared") else w

    base = sum(eff(i) for i in items if not i.get("worn") and not i.get("consumable"))
    worn = sum(eff(i) for i in items if i.get("worn"))
    consum = sum(eff(i) for i in items if i.get("consumable"))
    by_cat = {}
    for i in items:
        by_cat.setdefault(i.get("category", "Прочее"), 0)
        if not i.get("worn"):  # в категорийный подитог рюкзака «на себе» не входит
            by_cat[i.get("category", "Прочее")] += eff(i)
    return {"base_g": round(base), "worn_g": round(worn), "consumables_g": round(consum),
            "total_pack_g": round(base + consum), "skin_out_g": round(base + consum + worn),
            "by_category_g": {k: round(v) for k, v in by_cat.items()}}


def to_markdown(items, t, members):
    def g(w):
        return f"{w:.0f}" if w else "—"
    kg = lambda gr: f"{gr / 1000:.2f}"
    L = [f"# Снаряжение — весовой чеклист (на {members} чел., групповое поделено)", ""]
    cats = {}
    for i in items:
        cats.setdefault(i.get("category", "Прочее"), []).append(i)
    for cat, rows in cats.items():
        L += [f"## {cat} — {kg(t['by_category_g'][cat])} кг", "",
              "| Предмет | Модель | Вес, г | Кол-во | Итого, г | Примечания |",
              "|---|---|---|---|---|---|"]
        for i in rows:
            notes = []
            if i.get("weight_unknown"):
                notes.append("~вес неизвестен — взвесить")
            if i.get("worn"):
                notes.append("на себе")
            if i.get("consumable"):
                notes.append("расходник")
            if i.get("shared"):
                notes.append(f"групповое /{members}")
            if i.get("star"):
                notes.append("★ дешёвая экономия веса")
            w = i.get("weight_g") or 0
            eff = (w * (i.get("qty") or 1)) / (members if i.get("shared") else 1)
            L.append(f"| {i['item']} | {i.get('model', '')} | {g(w)} | "
                     f"{i.get('qty', 1)} | {eff:.0f} | {'; '.join(notes)} |")
        L.append("")
    L += ["## Итоги (посчитаны скриптом)", "",
          "| Показатель | кг |", "|---|---|",
          f"| Base Weight (рюкзак без расходников) | {kg(t['base_g'])} |",
          f"| Worn (на себе) | {kg(t['worn_g'])} |",
          f"| Consumables (еда+вода+газ на старте) | {kg(t['consumables_g'])} |",
          f"| **Total Pack (рюкзак на старте)** | **{kg(t['total_pack_g'])}** |",
          f"| Skin-out (всё на человеке) | {kg(t['skin_out_g'])} |", ""]
    base_kg = t["base_g"] / 1000
    verdict = next(label for limit, label in ORIENTERS if base_kg <= limit)
    L.append(f"**Оценка Base Weight {base_kg:.2f} кг: {verdict}.**")
    unknown = [i["item"] for i in items if i.get("weight_unknown")]
    if unknown:
        L += ["", "⚠️ Взвесить (вес неизвестен, в итогах = 0): " + ", ".join(unknown)]
    return "\n".join(L)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("gear", help="gear.json — список снаряжения")
    ap.add_argument("--members", type=int, default=1, help="участников (групповое делится)")
    ap.add_argument("--out", help="куда записать Снаряжение.md")
    args = ap.parse_args()

    items = load_items(args.gear)
    t = totals(items, args.members)
    md = to_markdown(items, t, args.members)
    if args.out:
        Path(args.out).write_text(md + "\n", encoding="utf-8")
    json.dump(t, sys.stdout, ensure_ascii=False, indent=2)
    print(f"\n✓ {len(items)} позиций; Base {t['base_g'] / 1000:.2f} кг, "
          f"Total Pack {t['total_pack_g'] / 1000:.2f} кг, Skin-out {t['skin_out_g'] / 1000:.2f} кг",
          file=sys.stderr)


if __name__ == "__main__":
    main()
