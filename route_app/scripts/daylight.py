#!/usr/bin/env python3
"""daylight.py — световой день и ночное небо для точек маршрута.

Всё считается кодом (астрономические формулы NOAA), ничего «из головы»:
- рассвет/закат и длина светового дня по координатам и датам (точность ~1–2 мин);
- фаза Луны и освещённость диска (синодический цикл от эталонного новолуния);
- пояс — IANA (Asia/Dushanbe и т.п.); на Windows нужен пакет tzdata
  (pip install tzdata), без него — фиксированный сдвиг --utc-offset.

Использование:
  python3 daylight.py points.json --start 2026-09-06 --end 2026-09-16 \
      --tz Asia/Dushanbe --md Световой_день.md
Вывод: JSON в stdout; --md — блок для гида (подмешивается в LLM-контекст).
"""
import argparse, json, math, sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

NEW_MOON_EPOCH = datetime(2000, 1, 6, 18, 14)  # эталонное новолуние (UTC)
SYNODIC = 29.530588853                        # синодический месяц, сутки

PHASES = [(1.84566, "Новолуние"), (5.53699, "Молодая"), (9.22831, "Первая четверть"),
          (12.91963, "Растущая"), (16.61096, "Полнолуние"), (20.30228, "Убывающая"),
          (23.99361, "Последняя четверть"), (27.68493, "Старая")]


def tz_offset(tzid, d, fallback_hours):
    if tzid and ZoneInfo:
        try:
            return datetime(d.year, d.month, d.day, 12, tzinfo=ZoneInfo(tzid)).utcoffset()
        except Exception as e:
            print(f"⚠️  Пояс {tzid}: {e} — использую сдвиг {fallback_hours:+} ч", file=sys.stderr)
    return timedelta(hours=fallback_hours)


def sun_times(d, lat, lon):
    """Рассвет/закат (UTC-минуты от полуночи) по формулам NOAA."""
    n = d.timetuple().tm_yday
    def calc(sunrise):
        lng_hour = lon / 15.0
        t = n + (6 - lng_hour) / 24 if sunrise else n + (18 - lng_hour) / 24
        m = 0.9856 * t - 3.289                       # средняя аномалия Солнца
        l = m + 1.916 * math.sin(math.radians(m)) + 0.020 * math.sin(math.radians(2 * m)) + 282.634
        l %= 360
        ra = math.degrees(math.atan(0.91764 * math.tan(math.radians(l)))) % 360
        ra = (ra + 90 * (l // 90 - ra // 90)) / 15.0  # в часы, в тот же квадрант
        sin_d = 0.39782 * math.sin(math.radians(l))
        cos_d = math.cos(math.asin(sin_d))
        cos_h = (math.cos(math.radians(90.833)) - sin_d * math.sin(math.radians(lat))) \
                / (cos_d * math.cos(math.radians(lat)))
        if not -1 <= cos_h <= 1:
            return None  # полярный день/ночь
        h = math.degrees(math.acos(cos_h)) / 15.0
        h = -h if sunrise else h   # на рассвете часовой угол отрицательный
        return (h + ra - 0.06571 * t - 6.622 - lng_hour) % 24 * 60  # UTC минуты
    rise, set_ = calc(True), calc(False)
    return rise, set_


def moon(d):
    """Возраст Луны (сутки), фаза, освещённость диска."""
    age = (datetime(d.year, d.month, d.day) - NEW_MOON_EPOCH).total_seconds() / 86400 % SYNODIC
    phase = next(name for edge, name in PHASES if age <= edge) if age <= PHASES[-1][0] else "Новолуние"
    illum = (1 - math.cos(math.radians(age / SYNODIC * 360))) / 2
    return round(age, 1), phase, round(illum * 100)


def fmt_utc(utc_min, offset):
    if utc_min is None:
        return "—"
    t = (datetime(2000, 1, 1) + timedelta(minutes=utc_min) + offset).time()
    return t.strftime("%H:%M")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("points", help="points.json (берётся центроид маршрута)")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--tz", default="Asia/Dushanbe", help="пояс IANA (нужен пакет tzdata на Windows)")
    ap.add_argument("--utc-offset", type=float, default=5.0, help="запасной сдвиг, часов")
    ap.add_argument("--md", help="куда записать markdown-блок «Световой день»")
    args = ap.parse_args()

    points = json.load(open(args.points, encoding="utf-8"))
    xy = [(p["lat"], p["lon"]) for p in points if "lat" in p]
    if not xy:
        sys.exit("В points.json нет координат")
    lat = sum(p[0] for p in xy) / len(xy)
    lon = sum(p[1] for p in xy) / len(xy)

    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    days = []
    d = start
    while d <= end:
        off = tz_offset(args.tz, d, args.utc_offset)
        rise, set_ = sun_times(d, lat, lon)
        age, phase, illum = moon(d)
        day_len = round(((set_ - rise) % 1440) / 60, 1) if rise is not None else None
        days.append({"date": d.isoformat(), "sunrise": fmt_utc(rise, off),
                     "sunset": fmt_utc(set_, off), "daylight_h": day_len,
                     "moon_age_d": age, "moon_phase": phase, "moon_illum_pct": illum})
        d += timedelta(days=1)

    report = {"lat": round(lat, 4), "lon": round(lon, 4), "tz": args.tz, "days": days}
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)

    if args.md:
        L = [f"## Световой день и ночное небо ({args.start} — {args.end})", "",
             f"_Расчёт для центра маршрута ({report['lat']}N, {report['lon']}E), "
             f"пояс {args.tz}; рассвет/закат по NOAA, фаза Луны — по синодическому циклу._", "",
             "| Дата | Рассвет | Закат | Световой день, ч | Луна | Освещённость |",
             "|---|---|---|---|---|---|"]
        for x in days:
            L.append(f"| {x['date']} | {x['sunrise']} | {x['sunset']} | {x['daylight_h']} | "
                     f"{x['moon_phase']} | {x['moon_illum_pct']}% |")
        Path(args.md).write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"\n✓ {len(days)} дней; центр маршрута {report['lat']}N, {report['lon']}E; "
          f"пояс {args.tz}", file=sys.stderr)


if __name__ == "__main__":
    main()
