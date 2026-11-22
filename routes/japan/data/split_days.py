#!/usr/bin/env python3
"""Разрезание трека Накахэти на дневные сегменты (день 5 и день 6).

Точка разреза — ближайшая к Цугизакура-одзи (33.8285044, 135.6341448,
S-038) точка nakahechi_final.gpx; индекс найден кодом на этапе T-004 и
проверен (41 м от святыни, отметка 16,43 км). Сегменты нужны генератору
make_guide_html.py (профиль высот строится по track.gpx проекта) и
будущему KML по дням (T-006).

Использование: python3 split_days.py
Вход:  nakahechi_final.gpx
Выход: day5_takijiri_tsugizakura.gpx, day6_tsugizakura_hongu.gpx
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "route_app" / "scripts"))
import gpx_analyze as ga  # noqa: E402 — общий движок проекта

TSUGIZAKURA = (33.8285044, 135.6341448)  # S-038, OSM/Nominatim


def write_gpx(points, path, name):
    """Минимальный GPX 1.1 со списком (lat, lon, ele)."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<gpx version="1.1" creator="routes/japan split_days" '
             'xmlns="http://www.topografix.com/GPX/1/1">',
             f"  <trk><name>{name}</name><trkseg>"]
    for lat, lon, ele in points:
        lines.append(f'    <trkpt lat="{lat:.6f}" lon="{lon:.6f}">'
                     f"<ele>{ele:.0f}</ele></trkpt>")
    lines.append("  </trkseg></trk>\n</gpx>")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main():
    """Режет трек на два дневных сегмента и печатает контрольные числа."""
    trkpts, _ = ga.load_gpx("nakahechi_final.gpx")
    dist = ga.cumulative(trkpts)
    cut = ga.project(trkpts, dist, *TSUGIZAKURA)["index"]
    if trkpts[cut][2] is None:
        sys.exit("трек без высот — сначала process_tracks.py")
    d5 = trkpts[:cut + 1]
    d6 = trkpts[cut:]
    write_gpx(d5, "day5_takijiri_tsugizakura.gpx",
              "Nakahechi day 5 Takijiri-Tsugizakura")
    write_gpx(d6, "day6_tsugizakura_hongu.gpx",
              "Nakahechi day 6 Tsugizakura-Hongu")
    for label, seg in (("день 5", d5), ("день 6", d6)):
        km = sum(ga.haversine(*seg[i][:2], *seg[i + 1][:2])
                 for i in range(len(seg) - 1)) / 1000
        up = sum(max(0.0, seg[i + 1][2] - seg[i][2]) for i in range(len(seg) - 1))
        down = sum(max(0.0, seg[i][2] - seg[i + 1][2]) for i in range(len(seg) - 1))
        print(f"{label}: {len(seg)} точек, {km:.2f} км, +{up:.0f}/-{down:.0f} м")


if __name__ == "__main__":
    main()
