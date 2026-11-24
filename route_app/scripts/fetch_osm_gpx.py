#!/usr/bin/env python3
"""Сборка GPX из OSM-отношения (Overpass API) для маршрута Японии.

Скачивает relation по id, собирает геометрии участков (way) в один трек
и пишет GPX 1.1 (lat/lon/ele, если ele есть в тегах — иначе 0).
Использование: python3 fetch_osm_gpx.py <relation_id> <out.gpx> <name>
"""
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET

OVERPASS = ["https://overpass.kumi.systems/api/interpreter",
            "https://overpass-api.de/api/interpreter"]  # зеркала: kumi быстрый, de — запасной


def fetch_relation(rel_id: int) -> dict:
    """Возвращает JSON Overpass с полной геометрией отношения (зеркала по очереди).
    GET ?data= + User-Agent: POST без UA отклоняется зеркалами (HTTP 406)."""
    query = f"[out:json][timeout:60];relation({rel_id});out geom;"
    last = None
    for mirror in OVERPASS:
        url = mirror + "?data=" + urllib.parse.quote(query)
        req = urllib.request.Request(url, headers={"User-Agent": "KIMIK3-route-guide/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last = e
            print(f"⚠️  Overpass {mirror.split('/')[2]}: {e} — пробую зеркало",
                  file=sys.stderr)
    sys.exit(f"⚠️  Overpass недоступен (все зеркала): {last}")


def relation_to_points(data: dict) -> list:
    """Собирает точки всех way-участков отношения в один список (lat, lon)."""
    pts = []
    for el in data.get("elements", []):
        if el.get("type") != "relation":
            continue
        for member in el.get("members", []):
            if member.get("type") != "way" or "geometry" not in member:
                continue
            for node in member["geometry"]:
                pts.append((node["lat"], node["lon"]))
    return pts


def write_gpx(points: list, path: str, name: str) -> None:
    """Пишет точки в GPX 1.1 (trkpt lat/lon, ele=0 при отсутствии данных)."""
    gpx = ET.Element(
        "gpx",
        {
            "version": "1.1",
            "creator": "routes/japan fetch_osm_gpx",
            "xmlns": "http://www.topografix.com/GPX/1/1",
        },
    )
    trk = ET.SubElement(gpx, "trk")
    ET.SubElement(trk, "name").text = name
    seg = ET.SubElement(trk, "trkseg")
    for lat, lon in points:
        p = ET.SubElement(seg, "trkpt", {"lat": f"{lat:.6f}", "lon": f"{lon:.6f}"})
        ET.SubElement(p, "ele").text = "0"
    ET.ElementTree(gpx).write(path, encoding="utf-8", xml_declaration=True)


def main() -> None:
    """Точка входа: relation_id, выходной файл, имя трека из argv."""
    rel_id, out, name = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    data = fetch_relation(rel_id)
    pts = relation_to_points(data)
    if not pts:
        sys.exit("Точек не найдено — проверьте id отношения и ответ Overpass")
    write_gpx(pts, out, name)
    print(f"OK: {len(pts)} точек -> {out}")


if __name__ == "__main__":
    main()
