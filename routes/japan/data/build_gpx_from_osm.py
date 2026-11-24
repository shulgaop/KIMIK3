#!/usr/bin/env python3
"""Сборка GPX из файла OSM API (/relation/<id>/full).

Парсит узлы и линии, берёт way-участки отношения (кроме ролей
excursion/approach — это ответвления, а не основная линия), склеивает их
в цепочку по совпадающим концам (с разворотом при необходимости)
и пишет GPX 1.1 без высот (в OSM их нет — высоты добавит SRTM/DEM-этап
либо останутся 0; километраж считается по координатам).

Использование: python3 build_gpx_from_osm.py <in.osm> <out.gpx> <name>
"""
import sys
import xml.etree.ElementTree as ET

SKIP_ROLES = {"excursion", "approach"}  # боковые выходы, не линия маршрута


def parse_osm(path):
    """Возвращает (узлы, линии, список way-участков отношения в порядке членов)."""
    root = ET.parse(path).getroot()
    nodes = {n.get("id"): (float(n.get("lat")), float(n.get("lon")))
             for n in root.findall("node")}
    ways = {}
    for w in root.findall("way"):
        ways[w.get("id")] = [nd.get("ref") for nd in w.findall("nd")]
    rel = root.find("relation")
    member_way_ids = []
    for m in rel.findall("member"):
        if m.get("type") == "way" and m.get("role", "") not in SKIP_ROLES:
            member_way_ids.append(m.get("ref"))
    return nodes, ways, member_way_ids


def chain_segments(segments):
    """Склеивает список сегментов в цепочку по совпадающим концам.

    Сегменты в route-отношениях OSM не гарантированно упорядочены и могут
    быть развёрнуты; жадно достраиваем цепочку от первого сегмента.
    Возвращает единый список id узлов (или None, если цепочка рвётся).
    """
    pool = [list(s) for s in segments]
    chain = pool.pop(0)
    while pool:
        end = chain[-1]
        for i, s in enumerate(pool):
            if s[0] == end:
                chain.extend(s[1:])
                pool.pop(i)
                break
            if s[-1] == end:
                chain.extend(reversed(s[:-1]))
                pool.pop(i)
                break
        else:
            # конец не срастается — пробуем достроить от начала цепочки
            start = chain[0]
            for i, s in enumerate(pool):
                if s[-1] == start:
                    chain = s[:-1] + chain
                    pool.pop(i)
                    break
                if s[0] == start:
                    chain = list(reversed(s[1:])) + chain
                    pool.pop(i)
                    break
            else:
                return None  # разрыв: данных недостаточно для единой линии
    return chain


def main():
    """Точка входа: читает OSM XML, пишет GPX, печатает число точек."""
    src, out, name = sys.argv[1], sys.argv[2], sys.argv[3]
    nodes, ways, member_ids = parse_osm(src)
    segments = [ways[w] for w in member_ids if w in ways]
    chain = chain_segments(segments)
    if chain is None:
        sys.exit("Цепочка не срастается — проверьте состав отношения вручную")
    gpx = ET.Element("gpx", {
        "version": "1.1", "creator": "routes/japan build_gpx_from_osm",
        "xmlns": "http://www.topografix.com/GPX/1/1"})
    trk = ET.SubElement(gpx, "trk")
    ET.SubElement(trk, "name").text = name
    seg = ET.SubElement(trk, "trkseg")
    skipped = 0
    for nid in chain:
        if nid not in nodes:
            skipped += 1
            continue
        lat, lon = nodes[nid]
        p = ET.SubElement(seg, "trkpt", {"lat": f"{lat:.6f}", "lon": f"{lon:.6f}"})
        ET.SubElement(p, "ele").text = "0"
    ET.ElementTree(gpx).write(out, encoding="utf-8", xml_declaration=True)
    print(f"OK: {len(chain) - skipped} точек -> {out} (пропущено {skipped})")


if __name__ == "__main__":
    main()
