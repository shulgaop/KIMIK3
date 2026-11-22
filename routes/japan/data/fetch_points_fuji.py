#!/usr/bin/env python3
"""Сбор координат точек дня 2 (тропа Yoshida, Фудзи) из Nominatim (OSM).

Результат: points_fuji.json — {name, jp, lat, lon, ele, track_km, off_track_m};
ele восстанавливается проекцией на трек fuji_yoshida_final.gpx (SRTM 90 м).

Использование: python3 fetch_points_fuji.py
Вход:  fuji_yoshida_final.gpx (в этом же каталоге)
Выход: points_fuji.json
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "route_app" / "scripts"))
import gpx_analyze as ga  # noqa: E402 — общий движок проекта

# Очередь запросов: (имя в гиде, запрос Nominatim). Большинство станций
# Nominatim не знает или путает с тёзками — координаты из OSM (Overpass,
# запрос 2026-11-23): 七合目日の出館 3028998900, 本八合目 474994719,
# 九合目 3042913522, 剣ヶ峰 873531353; автовокзал — узел 5057904921.
OSM_FIXUPS = {
    "富士スバルライン五合目": (35.3940465, 138.7324500),
    "富士山七合目": (35.3786924, 138.7444031),
    "富士山八合目": (35.3690313, 138.7391872),
    "富士山九合目": (35.3670197, 138.7351432),
    "剣ヶ峰": (35.3606812, 138.7273506),
}
QUERIES = [
    ("5-я станция Fuji Subaru Line", "富士スバルライン五合目"),
    ("7-я станция (Хи-но-дэкан)", "富士山七合目"),
    ("8-я станция (хижины)", "富士山八合目"),
    ("9-я станция Yoshida", "富士山九合目"),
    ("Вершина Фудзи (Кэнгаминэ)", "剣ヶ峰"),
]
OFF_TRACK_MAX_M = 1500
UA = "KIMIK3-japan-route/1.0 (route research)"


def nominatim(query):
    """Первый результат Nominatim по запросу: (lat, lon, display_name)."""
    url = ("https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=jp&q="
           + urllib.parse.quote(query))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    if not data:
        return None
    d = data[0]
    return float(d["lat"]), float(d["lon"]), d["display_name"]


def collect(trkpts, dist, name, jp, lat, lon, disp=""):
    """Проецирует точку на трек и возвращает запись для points_fuji.json."""
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
    """Собирает координаты, проецирует на трек, пишет points_fuji.json."""
    trkpts, _ = ga.load_gpx("fuji_yoshida_final.gpx")
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
    Path("points_fuji.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ points_fuji.json: {len(out)} точек")


if __name__ == "__main__":
    main()
