#!/usr/bin/env python3
"""currency.py — курсы любых национальных валют на дату запроса (F10).

Источник: open.er-api.com (бесплатно, без ключа; курсы обновляются раз в сутки).
Пересчёт — из четырёх опорных валют сразу: USD, EUR, BYN, RUB (можно сузить
через --from). Целевые валюты — любые ISO-коды (--currencies JPY,KZT,...).

Выдача:
- JSON в stdout: {currency: {per_USD, per_EUR, per_BYN, per_RUB}};
- Деньги.md (--md) — таблица для гида «Логистика/деньги» (в LLM-контексте);
- используется budget.py для конвертации итогов (fetch_rates(base)).

Использование:
  python3 currency.py --currencies JPY,UZS,TJS --md Деньги.md
  python3 currency.py --currencies KZT --from EUR,BYN
"""
import argparse, json, sys, urllib.request
from pathlib import Path

API = "https://open.er-api.com/v6/latest"
FROM_DEFAULT = ["USD", "EUR", "BYN", "RUB"]  # опорные валюты пересчёта


def fetch_rates(base):
    """Курсы «1 <base> = X <любая валюта>» на сегодня. Бросает SystemExit при сбое."""
    url = f"{API}/{base}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.load(r)
    except Exception as e:
        sys.exit(f"⚠️  Курсы недоступны ({url}): {e}")
    if data.get("result") != "success":
        sys.exit(f"⚠️  API вернуло ошибку: {data.get('error-type', data)}")
    return data


def build_rows(codes, from_list):
    """Таблица: каждая целевая валюта против каждой опорной."""
    by_base = {}
    date_utc = ""
    for base in from_list:
        data = fetch_rates(base)
        by_base[base] = data["rates"]
        date_utc = data.get("time_last_update_utc", "")[:16]
    rows = []
    for c in codes:
        if c not in by_base[from_list[0]]:
            print(f"⚠️  Неизвестный код валюты: {c}", file=sys.stderr)
            continue
        row = {"currency": c}
        for base in from_list:
            row[f"per_{base}"] = round(by_base[base][c], 4)
        rows.append(row)
    return rows, date_utc


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--currencies", required=True,
                    help="любые ISO-коды через запятую: JPY,KZT,UZS,TJS…")
    ap.add_argument("--from", dest="from_list", default=",".join(FROM_DEFAULT),
                    help="опорные валюты (по умолчанию USD,EUR,BYN,RUB)")
    ap.add_argument("--md", help="куда записать markdown-блок «Деньги»")
    args = ap.parse_args()

    codes = [c.strip().upper() for c in args.currencies.split(",") if c.strip()]
    from_list = [c.strip().upper() for c in args.from_list.split(",") if c.strip()]
    rows, date_utc = build_rows(codes, from_list)

    json.dump({"from": from_list, "date_utc": date_utc,
               "source": "open.er-api.com", "rates": rows},
              sys.stdout, ensure_ascii=False, indent=2)

    if args.md:
        L = [f"## Деньги (курсы на {date_utc} UTC)", "",
             "_Источник: open.er-api.com. Перепроверить перед вылетом._", "",
             "| Валюта | " + " | ".join(f"1 {b}" for b in from_list) + " |",
             "|---|" + "---|" * len(from_list)]
        for r in rows:
            L.append(f"| {r['currency']} | " +
                     " | ".join(str(r[f"per_{b}"]) for b in from_list) + " |")
        Path(args.md).write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"\n✓ Курсы на {date_utc} для {len(rows)} валют из {', '.join(from_list)}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
