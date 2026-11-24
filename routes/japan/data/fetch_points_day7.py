#!/usr/bin/env python3
"""Сбор координат точек дня 7 (Когумотори-гоэ: Хонгу → Когути) из Nominatim (OSM).

Результат: points_day7.json — {name, jp, lat, lon, ele, track_km, off_track_m};
ele восстанавливается проекцией на трек day7_hongu_koguchi.gpx (SRTM 90 м).

Использование: python3 fetch_points_day7.py
Вход:  day7_hongu_koguchi.gpx (в этом же каталоге)
Выход: points_day7.json
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "route_app" / "scripts"))
import gpx_analyze as ga  # noqa: E402 — общий движок проекта

# Очередь запросов: (имя в гиде, запрос Nominatim). Японские написания
# сверены с официальными картами tb-kumano (S-041).
# Точные координаты из OSM (узлы Overpass вдоль трека, запрос 2026-11-23):
# Sakura chaya 3212482193, Ishido-chaya 5104319953, Hyakken-gura 5104319753,
# Sai-no-Kawara 5104319752, Matsuhata 3210797194, Ukegawa 5104407621,
# Koguchi Bus stop 5114931423. Nominatim этих точек не знает (тёзки).
OSM_FIXUPS = {
    "請川": (33.8215203, 135.7886927),
    "賽の河原": (33.7910737, 135.8206240),
    "石堂茶屋跡": (33.7881209, 135.8191559),
    "百間ぐら": (33.8004762, 135.8204012),
    "松畑茶屋跡": (33.8096836, 135.8163283),
    "桜茶屋跡": (33.7780552, 135.8317431),
    "小口": (33.7582994, 135.8404768),
}
QUERIES = [
    ("Укэгава (вход на тропу)", "請川"),
    ("Мацухата-дзяя", "松畑茶屋跡"),
    ("Хяккэн-гура (смотровая)", "百間ぐら"),
    ("Сай-но-Кавара Дзидзо", "賽の河原"),
    ("Исидо-дзяя", "石堂茶屋跡"),
    ("Сакура-дзяя", "桜茶屋跡"),
    ("Когути (автобус)", "小口"),
]
OFF_TRACK_MAX_M = 2000
UA = "KIMIK3-japan-route/1.0 (route research)"


def nominatim(query):
    """Первый результат Nominatim по запросу: (lat, lon, display_name)."""
    url = ("https://nominatim.openstreetmap.org/search?format=json&limit=1&q="
           + urllib.parse.quote(query))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    if not data:
        return None
    d = data[0]
    return float(d["lat"]), float(d["lon"]), d["display_name"]


def collect(trkpts, dist, name, jp, lat, lon, disp=""):
    """Проецирует точку на трек и возвращает запись для points_day7.json."""
    pr = ga.project(trkpts, dist, lat, lon)
    ele = round(trkpts[pr["index"]][2]) if pr["off_track_m"] < 500 else None
    rec = {"name": name, "jp": jp, "lat": lat, "lon": lon,
           "ele": ele,
           "track_km": round(dist[pr["index"]] / 1000, 2),
           "off_track_m": round(pr["off_track_m"])}
    flag = "" if pr["off_track_m"] < 500 else "  (в стороне от трека)"
    print(f"  {name}: {lat:.5f},{lon:.5f} → {rec['track_km']} км{flag}")
    return rec


def main():
    """Собирает координаты, проецирует на трек, пишет points_day7.json."""
    trkpts, _ = ga.load_gpx("day7_hongu_koguchi.gpx")
    dist = ga.cumulative(trkpts)
    out = []
    for name, query in QUERIES:
        if query in OSM_FIXUPS:
            lat, lon = OSM_FIXUPS[query]
            out.append(collect(trkpts, dist, name, query, lat, lon))
            continue
        res = nominatim(query)
        time.sleep(1.2)  # лимит Nominatim — 1 запрос/с
        if not res:
            print(f"  ⚠️  не найдено: {query}", file=sys.stderr)
            continue
        lat, lon, disp = res
        out.append(collect(trkpts, dist, name, query, lat, lon, disp))
    out.sort(key=lambda r: r["track_km"])
    Path("points_day7.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ points_day7.json: {len(out)} точек")


if __name__ == "__main__":
    main()
