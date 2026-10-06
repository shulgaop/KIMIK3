#!/usr/bin/env python3
"""weather.py — погодный движок (F3) для точек маршрута.

Источник — Open-Meteo (бесплатно, без API-ключа):
- прогноз:  api.open-meteo.com/v1/forecast (ежедневные значения, до ~16 суток);
- климат:   archive-api.open-meteo.com/v1/archive (ERA5) — нормы по тем же
            календарным датам за N прошлых лет + дата перепроверки;
- факт:     тот же архив ERA5 для прошедших дат (реанализ, НЕ наземные
            наблюдения — так и пишем в отчёте).

Температуры пересчитываются на высоту точки градиентом −0,6 °C/100 м
от высоты сетки модели (elevation из ответа API):
  t_точки = t_сетки − 0,6 × (высота_точки − высота_сетки) / 100

Использование:
  python3 weather.py points.json --start 2026-09-06 --end 2026-09-16
  python3 weather.py points.json --start 2026-09-06 --end 2026-09-16 \
      --out погода.json --md Погода.md --years 10

points.json: [{"name": "Кемп Куликалон", "lat": 39.2551, "lon": 68.1723, "ele": 2850}, ...]
Поле ele необязательно: без него берётся высота сетки модели (поправка = 0).
Вывод: JSON-отчёт в stdout (человекочитаемая сводка — в stderr).
"""
import argparse, json, sys, time, urllib.parse, urllib.request
from datetime import date, timedelta

LAPSE_C_PER_100M = 0.6   # вертикальный градиент температуры
FORECAST_DAYS = 14       # горизонт «честного» прогноза (ТЗ: 10–14 дней)
API_FORECAST = "https://api.open-meteo.com/v1/forecast"
API_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"

DAILY_COMMON = ["temperature_2m_max", "temperature_2m_min",
                "precipitation_sum", "wind_speed_10m_max",
                "wind_direction_10m_dominant"]


def fetch(api, lat, lon, start, end, extra=()):
    """Запрос daily-параметров Open-Meteo. Возвращает разобранный JSON."""
    params = {
        "latitude": lat, "longitude": lon,
        "daily": ",".join(DAILY_COMMON + list(extra)),
        "wind_speed_unit": "ms", "timezone": "auto",
        "start_date": start.isoformat(), "end_date": end.isoformat(),
    }
    url = f"{api}?{urllib.parse.urlencode(params)}"
    for attempt, pause in enumerate((2, 5, 10), start=1):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 3:
                sys.exit(f"⚠️  Open-Meteo недоступен ({api}): {e}")
            print(f"⚠️  {api}: {e} — повтор через {pause} с", file=sys.stderr)
            time.sleep(pause)


def lapse_correct(t, ele_point, ele_grid):
    """Пересчёт температуры на высоту точки градиентом −0,6 °C/100 м."""
    if t is None:
        return None
    return round(t - LAPSE_C_PER_100M * (ele_point - ele_grid) / 100, 1)


def compass(deg):
    rumbs = ["С", "ССВ", "СВ", "ВСВ", "В", "ВЮВ", "ЮВ", "ЮЮВ",
             "Ю", "ЮЮЗ", "ЮЗ", "ЗЮЗ", "З", "ЗСЗ", "СЗ", "ССЗ"]
    return rumbs[round((deg or 0) / 22.5) % 16]


def mode_for(start, end, today):
    """Режим по датам: fact — весь интервал в прошлом; forecast — старт внутри
    горизонта прогноза; climate — всё дальше горизонта."""
    if end < today:
        return "fact"
    if start <= today + timedelta(days=FORECAST_DAYS):
        return "forecast"
    return "climate"


def days_from_daily(daily, ele_point, ele_grid, with_prob):
    """Список дней из daily-блока API с поправкой температур на высоту."""
    days = []
    for i, d in enumerate(daily.get("time", [])):
        day = {
            "date": d,
            "tmin": lapse_correct(daily["temperature_2m_min"][i], ele_point, ele_grid),
            "tmax": lapse_correct(daily["temperature_2m_max"][i], ele_point, ele_grid),
            "precip_mm": daily["precipitation_sum"][i],
            "wind_max_ms": daily["wind_speed_10m_max"][i],
            "wind_dir": compass(daily["wind_direction_10m_dominant"][i]),
        }
        if with_prob:
            day["precip_prob_pct"] = daily["precipitation_probability_max"][i]
        days.append(day)
    return days


def point_fact(p, start, end):
    """Факт (реанализ ERA5) за прошедшие даты."""
    r = fetch(API_ARCHIVE, p["lat"], p["lon"], start, end)
    grid = r.get("elevation", 0)
    ele = p.get("ele") or grid
    return {"ele_grid": round(grid), "ele_point": ele,
            "days": days_from_daily(r["daily"], ele, grid, with_prob=False)}


def point_forecast(p, start, end, today):
    """Прогноз; дни за пределами горизонта API отсутствуют (partial=True)."""
    api_end = min(end, today + timedelta(days=FORECAST_DAYS + 1))
    r = fetch(API_FORECAST, p["lat"], p["lon"], max(start, today), api_end,
              extra=["precipitation_probability_max"])
    grid = r.get("elevation", 0)
    ele = p.get("ele") or grid
    days = days_from_daily(r["daily"], ele, grid, with_prob=True)
    covered_from = date.fromisoformat(days[0]["date"]) if days else api_end
    covered_to = date.fromisoformat(days[-1]["date"]) if days else today
    return {"ele_grid": round(grid), "ele_point": ele,
            "days": days, "covered_from": covered_from.isoformat(),
            "covered_to": covered_to.isoformat(),
            "partial": covered_from > start or covered_to < end}


def point_climate(p, start, end, today, years):
    """Климатические нормы ERA5 по тем же календарным датам за `years` прошлых лет."""
    n_days = (end - start).days + 1
    samples = {}  # индекс дня -> {"tmax": [...], "tmin": [...], "precip": [...]}
    grid = ele = None
    for y in range(today.year - years, today.year):
        try:
            s = date(y, start.month, start.day)
        except ValueError:  # 29 февраля в невисокосном году
            continue
        r = fetch(API_ARCHIVE, p["lat"], p["lon"], s, s + timedelta(days=n_days - 1))
        if grid is None:
            grid = r.get("elevation", 0)
            ele = p.get("ele") or grid
        for i in range(min(n_days, len(r["daily"].get("time", [])))):
            slot = samples.setdefault(i, {"tmax": [], "tmin": [], "precip": []})
            slot["tmax"].append(lapse_correct(r["daily"]["temperature_2m_max"][i], ele, grid))
            slot["tmin"].append(lapse_correct(r["daily"]["temperature_2m_min"][i], ele, grid))
            slot["precip"].append(r["daily"]["precipitation_sum"][i] or 0)
    days = []
    for i in range(n_days):
        slot = samples.get(i)
        if not slot:
            continue
        tmaxs = [t for t in slot["tmax"] if t is not None]
        tmins = [t for t in slot["tmin"] if t is not None]
        precips = slot["precip"]
        days.append({
            "date": (start + timedelta(days=i)).isoformat(),
            "tmin_mean": round(sum(tmins) / len(tmins), 1),
            "tmax_mean": round(sum(tmaxs) / len(tmaxs), 1),
            "tmin_abs": round(min(tmins), 1),
            "tmax_abs": round(max(tmaxs), 1),
            "precip_mean_mm": round(sum(precips) / len(precips), 1),
            "rain_years_pct": round(100 * sum(1 for x in precips if x >= 1) / len(precips)),
        })
    return {"ele_grid": round(grid or 0), "ele_point": ele,
            "climate_years": f"{today.year - years}–{today.year - 1}", "days": days}


def recheck_date(start, today):
    """Когда прогноз станет доступен: старт минус горизонт прогноза."""
    return (start - timedelta(days=FORECAST_DAYS)).isoformat()


def to_markdown(report):
    """Блок «Погода» для MD-гида: таблица по каждой точке."""
    lines = [f"## Погода ({report['route']['start']} — {report['route']['end']})",
             "", f"_{report['source']} {report['note']}_", ""]
    for p in report["points"]:
        lines.append(f"### {p['name']} ({p['ele_point']} м)")
        if report["mode"] == "climate":
            lines += ["", "| Дата | Ночь, °C (мин) | День, °C (макс) | Осадки, мм/сут | Годов с дождём |",
                      "|---|---|---|---|---|"]
            for d in p["days"]:
                lines.append(f"| {d['date']} | {d['tmin_mean']} ({d['tmin_abs']}) | "
                             f"{d['tmax_mean']} ({d['tmax_abs']}) | {d['precip_mean_mm']} | "
                             f"{d['rain_years_pct']}% |")
        else:
            prob = " | Вероятность осадков" if report["mode"] == "forecast" else ""
            lines += ["", f"| Дата | Ночь, °C | День, °C | Осадки, мм | Ветер, м/с{prob} |",
                      "|---|---|---|---|---|" + ("---|" if prob else "")]
            for d in p["days"]:
                row = (f"| {d['date']} | {d['tmin']} | {d['tmax']} | {d['precip_mm']} | "
                       f"{d['wind_max_ms']} {d['wind_dir']}")
                if report["mode"] == "forecast":
                    row += f" | {d.get('precip_prob_pct')}%"
                lines.append(row + " |")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("points", help="JSON с точками маршрута (name, lat, lon, ele?)")
    ap.add_argument("--start", required=True, help="первый день похода, ГГГГ-ММ-ДД")
    ap.add_argument("--end", required=True, help="последний день похода, ГГГГ-ММ-ДД")
    ap.add_argument("--out", help="куда записать JSON-отчёт (иначе только stdout)")
    ap.add_argument("--md", help="куда записать markdown-блок «Погода» для гида")
    ap.add_argument("--years", type=int, default=10, help="лет для климатических норм")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):  # Windows-консоль cp1251: не падать на −, ⚠, ✓
        sys.stdout.reconfigure(errors="replace")

    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    if end < start:
        sys.exit("--end раньше --start")
    today = date.today()
    mode = mode_for(start, end, today)
    points = json.load(open(args.points, encoding="utf-8"))

    report = {
        "generated_at": today.isoformat(),
        "route": {"start": args.start, "end": args.end},
        "lapse_C_per_100m": LAPSE_C_PER_100M,
        "mode": mode,
        "recheck_date": recheck_date(start, today) if mode == "climate" else None,
        "source": {"forecast": "Open-Meteo, прогноз.",
                   "climate": f"Open-Meteo, климатические нормы ERA5 за {args.years} лет.",
                   "fact": "Open-Meteo, архив ERA5 (реанализ)."}[mode],
        "note": {"forecast": "Температуры пересчитаны на высоту точек градиентом "
                             f"-{LAPSE_C_PER_100M} °C/100 м.",
                 "climate": "Прогноз ещё недоступен: нормы по тем же датам прошлых лет, "
                            "перепроверить в указанную дату. Температуры — на высоте точек.",
                 "fact": "Реанализ ERA5, НЕ наземные наблюдения; для блока «прогноз vs факт» "
                         "отчёта. Температуры — на высоте точек."}[mode],
        "points": [],
    }

    for p in points:
        if mode == "fact":
            data = point_fact(p, start, end)
        elif mode == "forecast":
            data = point_forecast(p, start, end, today)
        else:
            data = point_climate(p, start, end, today, args.years)
        report["points"].append({"name": p["name"], "lat": p["lat"], "lon": p["lon"], **data})
        if data.get("partial"):
            again = report["recheck_date"] or (today + timedelta(days=1)).isoformat()
            print(f"⚠️  «{p['name']}»: прогноз покрывает {data['covered_from']} — "
                  f"{data['covered_to']}, остальное — перепроверить {again}", file=sys.stderr)

    out = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(out + "\n")
    if args.md:
        open(args.md, "w", encoding="utf-8").write(to_markdown(report) + "\n")
    print(out)

    names = ", ".join(p["name"] for p in report["points"])
    print(f"\n✓ Режим «{mode}» ({report['source']}) Точки: {names}. "
          f"Дней: {(end - start).days + 1}." +
          (f" Перепроверка: {report['recheck_date']}." if report["recheck_date"] else ""),
          file=sys.stderr)


if __name__ == "__main__":
    main()
