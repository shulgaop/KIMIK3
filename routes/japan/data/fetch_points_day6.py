#!/usr/bin/env python3
"""Сбор координат точек дня 6 (Цугизакура → Хонгу) из Nominatim (OSM).

Результат: points_day6.json — список {name, jp, lat, lon, ele}, где ele
восстанавливается проекцией точки на трек nakahechi_final.gpx (SRTM 90 м),
а не выдумывается. Точки дальше OFF_TRACK_MAX_M от трека помечаются, но
сохраняются (вечерние точки Юноминэ — в стороне от трека).

Использование: python3 fetch_points_day6.py
Вход:  nakahechi_final.gpx (в этом же каталоге)
Выход: points_day6.json
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
    ("Цугизакура-одзи", "継桜王子"),
    ("Хоссиммон-одзи", "発心門王子"),
    ("Мидзуноми-одзи", "水呑王子"),
    ("Фусиогами-одзи", "伏拝王子"),
    ("Сангэн-дзяя (чайные домики)", "三軒茶屋跡"),
    ("Кумано Хонгу-тайся", "熊野本宮大社"),
    ("Оюнохара и О-Тории", "大斎原"),
    ("Юноминэ-онсэн", "湯の峰温泉"),
]
# Точные координаты из OSM (kumano_area.osm, узлы wayside_shrine) для точек,
# которых нет в Nominatim или где Nominatim находит тёзок вне Кумано:
# 水呑王子跡 (узел 33.8584282,135.7369837), Sangen jaya (33.8548710,135.7645992),
# 猪鼻王子 (33.8572134,135.7214344 — найден рядом с Хоссиммон, добавлен в гид).
OSM_FIXUPS = {
    "水呑王子": (33.8584282, 135.7369837),
    "三軒茶屋跡": (33.8548710, 135.7645992),
}
EXTRA_POINTS = [
    {"name": "Инохана-одзи", "jp": "猪鼻王子",
     "lat": 33.8572134, "lon": 135.7214344},
]
OFF_TRACK_MAX_M = 5000  # вечерний Юноминэ — за пределами трека, это ожидаемо
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
    """Проецирует точку на трек и возвращает запись для points_day6.json."""
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
    """Собирает координаты, проецирует на трек, пишет points_day6.json."""
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
    for extra in EXTRA_POINTS:
        out.append(collect(trkpts, dist, extra["name"], extra["jp"],
                           extra["lat"], extra["lon"]))
    out.sort(key=lambda r: r["track_km"])  # порядок прохождения по треку
    Path("points_day6.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ points_day6.json: {len(out)} точек")


if __name__ == "__main__":
    main()
