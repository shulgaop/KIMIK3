#!/usr/bin/env python3
"""Сбор координат точек дня 5 (Такидзири → Цугизакура) из Nominatim (OSM).

Результат: points_day5.json — список {name, jp, lat, lon, ele, track_km,
off_track_m}; ele восстанавливается проекцией на трек nakahechi_final.gpx
(SRTM 90 м), не выдумывается.

Использование: python3 fetch_points_day5.py
Вход:  nakahechi_final.gpx (в этом же каталоге)
Выход: points_day5.json
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
QUERIES = [
    ("Такидзири-одзи", "滝尻王子"),
    ("Тайнай-кугури", "胎内くぐり"),
    ("Такахара Кири-но-Сато", "高原熊野神社"),
    ("Гюба-додзи", "牛馬童子"),
    ("Чикатацию-одзи", "近露王子"),
    ("Цугизакура-одзи", "継桜王子"),
]
# Точные координаты из OSM для точек, которых нет в Nominatim или где
# Nominatim находит тёзок вне Кумано: 胎内くぐри — узел 13715153375
# «Tanai Kuguri Test of Faith» (33.7768832, 135.5049647), рядом с Такидзири.
OSM_FIXUPS = {
    "胎内くぐり": (33.7768832, 135.5049647),
}
OFF_TRACK_MAX_M = 1500  # Тайнай-кугури и Гюба-додзи — в стороне от линии трека
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
    """Проецирует точку на трек и возвращает запись для points_day5.json."""
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
    """Собирает координаты, проецирует на трек, пишет points_day5.json."""
    trkpts, _ = ga.load_gpx("nakahechi_final.gpx")
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
    out.sort(key=lambda r: r["track_km"])  # порядок прохождения по треку
    Path("points_day5.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ points_day5.json: {len(out)} точек")


if __name__ == "__main__":
    main()
