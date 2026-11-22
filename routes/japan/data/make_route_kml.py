#!/usr/bin/env python3
"""make_route_kml.py — единый KML маршрута Японии (все треки + точки).

Четыре независимых трека (Фудзи, дни 5–6 Накахэти, Когумотори дня 7)
с согласованными styleUrl (латиница) и всеми точками программы + городами.
Валидация — как в движке: XML, координаты lon,lat в общем bbox, styleUrl↔id.

Использование: python3 make_route_kml.py
Выход: ../generated/маршрут.kml
"""
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "route_app" / "scripts"))
_spec = importlib.util.spec_from_file_location(
    "make_kml", Path(__file__).resolve().parents[3] / "route_app" / "scripts" / "make_kml.py")
mk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mk)

DATA = Path(__file__).resolve().parent
OUT = DATA.parent / "generated" / "маршрут.kml"

# bbox всего маршрута (Фудзи + Кумано + коридор): юг, север, запад, восток
BBOX = (33.40, 35.80, 135.30, 139.80)

SEGMENTS = [
    ("fuji",    "День 2–3 · Фудзи (Yoshida)",   "fuji_yoshida_final.gpx",      0),
    ("kumano5", "День 5 · Такидзири → Цугизакура", "day5_takijiri_tsugizakura.gpx", 1),
    ("kumano6", "День 6 · Цугизакура → Хонгу",  "day6_tsugizakura_hongu.gpx",  2),
    ("kumano7", "День 7 · Когумотори (Хонгу → Когути)", "day7_hongu_koguchi.gpx", 3),
]
POINTS_FILES = ["points_fuji.json", "points_day5.json",
                "points_day6.json", "points_day7.json", "points_route.json"]


def main():
    parts = [mk.KML_HEADER, "<name>Япония 2027 · Фудзи и Кумано Кодо</name>"]
    for sid, label, gpx, ci in SEGMENTS:
        pts = mk.load_track(str(DATA / gpx))
        parts.append(mk.style_block(sid, mk.DAY_COLORS[ci % len(mk.DAY_COLORS)]))
        coords = " ".join(f"{lo},{la},{el}" for la, lo, el in pts)  # ВСЕГДА lon,lat!
        parts.append(f'<Placemark><name>{label}</name><styleUrl>#{sid}</styleUrl>'
                     f'<LineString><altitudeMode>clampToGround</altitudeMode>'
                     f'<coordinates>{coords}</coordinates></LineString></Placemark>')
    n_marks = 0
    for pf in POINTS_FILES:
        for p in json.loads((DATA / pf).read_text(encoding="utf-8")):
            if "lat" not in p:
                continue
            desc = p.get("jp", "")
            parts.append(f'<Placemark><name>{p["name"]}</name>'
                         f'<description>{desc}</description>'
                         f'<Point><coordinates>{p["lon"]},{p["lat"]},0</coordinates>'
                         f'</Point></Placemark>')
            n_marks += 1
    parts.append(mk.KML_FOOTER)
    OUT.write_text("\n".join(parts), encoding="utf-8")
    mk.validate(str(OUT), BBOX)
    print(f"✓ {OUT}: {len(SEGMENTS)} трека, {n_marks} точек")


if __name__ == "__main__":
    main()
