#!/usr/bin/env python3
"""make_kml.py — генерация KML для Google Earth из GPX + жёсткая валидация.

Правила (проверено боем на мобильном Google Earth — НЕ нарушать):
1. Координаты везде «долгота,широта,высота» (lon,lat). Перепутанный порядок =
   «маршрут улетел на другой континент».
2. ID стилей — только латиница без пробелов (day3, camp). Кириллица/пробел ->
   мобильный GE не резолвит стиль -> белые линии.
3. Внешние иконки (maps.google.com/...) ЗАПРЕЩЕНЫ — мобильный GE рисует красный X.
4. Цвета в формате KML aabbggrr (НЕ RGB).
5. altitudeMode = clampToGround.

Использование:
  python3 make_kml.py track.gpx out.kml --bbox 38.9 39.6 67.9 68.5
  python3 make_kml.py track.gpx out.kml --bbox S N W E --split-km 8 16 24  # дни по км
  python3 make_kml.py track.gpx out.kml --bbox S N W E --marks marks.json

marks.json: [{"name": "Кемп", "lat": ..., "lon": ..., "desc": "...", "style": "camp"}, ...]
Валидация запускается автоматически после записи: XML + bbox (точки и линии) + styleUrl↔id.
"""
import argparse, json, sys
import xml.etree.ElementTree as ET

NS = "{http://www.topografix.com/GPX/1/1}"
KML_HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
KML_FOOTER = "</Document></kml>"

DAY_COLORS = ["ff00c832", "ff3352db", "ff9933ff", "ff00a5ff", "ffff8800",
              "ff3399ff", "ffdb3356", "ff33a02c", "ff6a3d9a", "ffb15928"]


def load_track(path):
    pts = []
    for el in ET.parse(path).iter(NS + "trkpt"):
        ele_el = el.find(NS + "ele")
        pts.append((float(el.get("lat")), float(el.get("lon")),
                    float(ele_el.text) if ele_el is not None and ele_el.text else 0.0))
    return pts


def cumdist(pts):
    import math
    d, tot = [0.0], 0.0
    for i in range(1, len(pts)):
        p1, p2 = map(math.radians, pts[i - 1][:2]), map(math.radians, pts[i][:2])
        p1, p2 = list(p1), list(p2)
        a = math.sin((p2[0] - p1[0]) / 2) ** 2 + math.cos(p1[0]) * math.cos(p2[0]) * math.sin((p2[1] - p1[1]) / 2) ** 2
        tot += 2 * 6371000 * math.asin(math.sqrt(a))
        d.append(tot)
    return d


def style_block(sid, color):
    assert sid.replace("_", "").isalnum() and sid.isascii(), f"ID стиля '{sid}' должен быть латиницей"
    return (f'<Style id="{sid}"><LineStyle><color>{color}</color><width>4</width></LineStyle>'
            f'<IconStyle><color>{color}</color></IconStyle></Style>')


def build(pts, dist, splits_km, marks):
    out = [KML_HEADER, "<name>Маршрут</name>"]
    bounds = [0.0] + list(splits_km) + [dist[-1] / 1000 + 0.01]
    for day in range(len(bounds) - 1):
        sid = f"day{day + 1}"
        out.append(style_block(sid, DAY_COLORS[day % len(DAY_COLORS)]))
        seg = [(la, lo, el) for (la, lo, el), d in zip(pts, dist)
               if bounds[day] * 1000 <= d < bounds[day + 1] * 1000]
        if not seg:
            continue
        coords = " ".join(f"{lo},{la},{el}" for la, lo, el in seg)  # ВСЕГДА lon,lat!
        out.append(f'<Placemark><name>День {day + 1}</name><styleUrl>#{sid}</styleUrl>'
                   f'<LineString><altitudeMode>clampToGround</altitudeMode>'
                   f'<coordinates>{coords}</coordinates></LineString></Placemark>')
    for m in marks:
        out.append(f'<Placemark><name>{m["name"]}</name>'
                   f'<description>{m.get("desc", "")}</description>'
                   f'<Point><coordinates>{m["lon"]},{m["lat"]},0</coordinates></Point></Placemark>')
    out.append(KML_FOOTER)
    return "\n".join(out)


def validate(path, bbox):
    """XML валиден; все координаты (точки и линии) в bbox; styleUrl↔id."""
    s, n, w, e = bbox
    tree = ET.parse(path)
    root = tree.getroot()
    k = "{http://www.opengis.net/kml/2.2}"
    style_ids = {st.get("id") for st in root.iter(k + "Style")}
    used = set()
    bad = 0
    for su in root.iter(k + "styleUrl"):
        used.add(su.text.lstrip("#"))
    for c in root.iter(k + "coordinates"):
        for tok in c.text.split():
            lon, lat = float(tok.split(",")[0]), float(tok.split(",")[1])
            if not (s <= lat <= n and w <= lon <= e):
                bad += 1
                print(f"⚠️  Вне bbox: lat={lat}, lon={lon}", file=sys.stderr)
    missing = used - style_ids
    assert not missing, f"styleUrl без Style: {missing}"
    assert bad == 0, f"{bad} координат вне bbox — проверь порядок lon,lat!"
    print(f"✓ KML валиден: стилей {len(style_ids)}, координат в bbox — все", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gpx")
    ap.add_argument("out")
    ap.add_argument("--bbox", nargs=4, type=float, required=True,
                    metavar=("S", "N", "W", "E"), help="границы региона: юг север запад восток (шир/долг)")
    ap.add_argument("--split-km", nargs="*", type=float, default=[],
                    help="границы дней по километражу трека")
    ap.add_argument("--marks", help="JSON с Placemark-точками")
    args = ap.parse_args()

    pts = load_track(args.gpx)
    dist = cumdist(pts)
    marks = json.load(open(args.marks, encoding="utf-8")) if args.marks else []
    kml = build(pts, dist, args.split_km, marks)
    open(args.out, "w", encoding="utf-8").write(kml)
    validate(args.out, args.bbox)
    print(f"Записано: {args.out} ({dist[-1] / 1000:.1f} км, {len(marks)} точек)", file=sys.stderr)


if __name__ == "__main__":
    main()
