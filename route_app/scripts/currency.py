#!/usr/bin/env python3
"""currency.py — курсы валют стран маршрута на дату запроса (F10).

Источник: open.er-api.com (бесплатно, без ключа; курсы обновляются раз в сутки).
По ISO-кодам валют стран маршрута выдаёт:
- JSON в stdout;
- Деньги.md — блок для гида «Логистика/деньги» (подмешивается в LLM-контекст).

Использование:
  python3 currency.py --currencies BYN,UZS,TJS --md Деньги.md
  python3 currency.py --currencies BYN,UZS,TJS --base EUR
"""
import argparse, json, sys, urllib.request
from pathlib import Path

API = "https://open.er-api.com/v6/latest"


def fetch_rates(base):
    url = f"{API}/{base}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.load(r)
    except Exception as e:
        sys.exit(f"⚠️  Курсы недоступны ({url}): {e}")
    if data.get("result") != "success":
        sys.exit(f"⚠️  API вернуло ошибку: {data.get('error-type', data)}")
    return data


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--currencies", required=True,
                    help="ISO-коды через запятую: BYN,UZS,TJS (бел. рубль, сум, сомони)")
    ap.add_argument("--base", default="USD", help="базовая валюта (USD по умолчанию)")
    ap.add_argument("--also", default="EUR", help="вторая колонка (EUR; пусто — нет)")
    ap.add_argument("--md", help="куда записать markdown-блок «Деньги»")
    args = ap.parse_args()

    codes = [c.strip().upper() for c in args.currencies.split(",") if c.strip()]
    usd = fetch_rates("USD")
    rates = usd["rates"]
    date_utc = usd.get("time_last_update_utc", "")[:16]
    missing = [c for c in codes if c not in rates]
    if missing:
        print(f"⚠️  Неизвестные коды валют: {missing}", file=sys.stderr)

    eur = fetch_rates("EUR")["rates"] if args.also else {}
    rows = []
    for c in codes:
        if c not in rates:
            continue
        row = {"currency": c, "per_usd": round(rates[c], 2)}
        if args.also:
            row["per_eur"] = round(eur.get(c, 0), 2)
        rows.append(row)

    report = {"base": "USD", "also": args.also or None, "date_utc": date_utc,
              "source": "open.er-api.com", "rates": rows}
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)

    if args.md:
        L = [f"## Деньги (курсы на {date_utc} UTC)", "",
             "_Источник: open.er-api.com. Перепроверить перед вылетом._", "",
             f"| Валюта | 1 USD | 1 {args.also or '—'} |", "|---|---|---|"]
        for r in rows:
            L.append(f"| {r['currency']} | {r['per_usd']} | {r.get('per_eur', '—')} |")
        Path(args.md).write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"\n✓ Курсы на {date_utc}: " +
          ", ".join(f"1 USD = {r['per_usd']} {r['currency']}" for r in rows),
          file=sys.stderr)


if __name__ == "__main__":
    main()
