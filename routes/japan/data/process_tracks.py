#!/usr/bin/env python3
"""Постобработка треков маршрута Японии (воспроизводимо, без ручных шагов).

1) nakahechi_osm.gpx — разворот в направлении паломников (Такидзири → Хонгу):
   собранная из OSM цепочка идёт от Хонгу (конец склейки), разворачиваем.
2) fuji_kawaguchiko_osm.gpx (OSM relation 223095, 河口湖ルート「上り」) —
   официальная тропа от 5-й станции до вершины; к ней добавляем коннектор
   от автовокзала 5-й станции: OSM way 110252407 из fuji_area2.osm
   (станция → начало тропы), первой точкой ставим автовокзал.
   Исторический Yoshidaguchi (fuji_yoshida_osm.gpx) остаётся справочным
   источником: пользователь стартует автобусом на 5-й станции, а не в городе.
3) Обогащение высотами из OpenTopoData (SRTM 90 m, пакетами по 100 точек):
   OSM не хранит ele, а профиль высот нужен для gpx_analyze и SVG-профиля.

Использование: python3 process_tracks.py
Входы:  nakahechi_osm.gpx, fuji_kawaguchiko_osm.gpx, fuji_area2.osm
        (в этом же каталоге)
Выходы: nakahechi_final.gpx, fuji_yoshida_final.gpx
"""
import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

NS = "{http://www.topografix.com/GPX/1/1}"
# Автовокзал 5-й станции Fuji Subaru Line (OSM node «富士五合目バス停»),
# сюда прибывает автобус Синдзюку → 5-я станция; старт пешей части.
FIFTH_STATION_BUS = (35.3940465, 138.7324500)
# OSM way, соединяющий комплекс 5-й станции с началом тропы Кавагутико.
CONNECTOR_WAY_ID = "110252407"
OTD_URL = "https://api.opentopodata.org/v1/srtm90m"


def load_points(path):
    """Возвращает список [lat, lon, ele] из trkpt GPX-файла."""
    pts = []
    for p in ET.parse(path).iter(NS + "trkpt"):
        ele = p.find(NS + "ele")
        pts.append([float(p.get("lat")), float(p.get("lon")),
                    float(ele.text) if ele is not None and ele.text else 0.0])
    return pts


def load_connector(osm_path, way_id):
    """Извлекает точки OSM way-коннектора как список [lat, lon, 0]."""
    root = ET.parse(osm_path).getroot()
    nodes = {n.get("id"): (float(n.get("lat")), float(n.get("lon")))
             for n in root.iter("node")}
    for w in root.iter("way"):
        if w.get("id") == way_id:
            pts = [list(nodes[nd.get("ref")]) + [0.0]
                   for nd in w.iter("nd") if nd.get("ref") in nodes]
            if not pts:
                sys.exit(f"way {way_id} без известных узлов")
            return pts
    sys.exit(f"way {way_id} не найден в {osm_path}")


def save_gpx(points, path, name):
    """Пишет список [lat, lon, ele] в GPX 1.1."""
    gpx = ET.Element("gpx", {
        "version": "1.1", "creator": "routes/japan process_tracks",
        "xmlns": "http://www.topografix.com/GPX/1/1"})
    trk = ET.SubElement(gpx, "trk")
    ET.SubElement(trk, "name").text = name
    seg = ET.SubElement(trk, "trkseg")
    for lat, lon, ele in points:
        p = ET.SubElement(seg, "trkpt", {"lat": f"{lat:.6f}", "lon": f"{lon:.6f}"})
        ET.SubElement(p, "ele").text = f"{ele:.0f}"
    ET.ElementTree(gpx).write(path, encoding="utf-8", xml_declaration=True)


def enrich_elevation(points, pause=1.0):
    """Проставляет ele из OpenTopoData SRTM 90 m (до 100 точек на запрос)."""
    for start in range(0, len(points), 100):
        chunk = points[start:start + 100]
        locs = "|".join(f"{lat:.6f},{lon:.6f}" for lat, lon, _ in chunk)
        url = OTD_URL + "?locations=" + urllib.parse.quote(locs)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                for pt, r in zip(chunk, data["results"]):
                    if r.get("elevation") is not None:
                        pt[2] = float(r["elevation"])
                break
            except Exception as e:  # сеть/лимит — повтор с паузой
                print(f"  retry {attempt + 1} ({e})", file=sys.stderr)
                time.sleep(5 * (attempt + 1))
        else:
            sys.exit("OpenTopoData недоступен — прогон повторить позже")
        time.sleep(pause)  # вежливый темп к публичному API


def main():
    """Выполняет разворот, сборку Фудзи и обогащение; печатает контрольные числа."""
    naka = load_points("nakahechi_osm.gpx")
    naka.reverse()  # OSM-цепочка собрана от Хонгу; маршрут идёт от Такидзири
    enrich_elevation(naka)
    save_gpx(naka, "nakahechi_final.gpx", "Kumano Kodo Nakahechi Takijiri-Hongu")
    print(f"nakahechi: {len(naka)} точек, старт {naka[0][:2]}, финиш {naka[-1][:2]},"
          f" ele {min(p[2] for p in naka):.0f}–{max(p[2] for p in naka):.0f} м")

    fuji = load_points("fuji_kawaguchiko_osm.gpx")
    connector = load_connector("fuji_area2.osm", CONNECTOR_WAY_ID)
    # Коннектор должен стыковаться с началом тропы; при обратном порядке
    # точек в way разворачиваем.
    if abs(connector[0][0] - fuji[0][0]) + abs(connector[0][1] - fuji[0][1]) < \
       abs(connector[-1][0] - fuji[0][0]) + abs(connector[-1][1] - fuji[0][1]):
        connector.reverse()
    fuji = [[FIFTH_STATION_BUS[0], FIFTH_STATION_BUS[1], 0.0]] + connector + fuji
    enrich_elevation(fuji)
    save_gpx(fuji, "fuji_yoshida_final.gpx", "Mt. Fuji Yoshida 5th Station-Summit")
    print(f"fuji: {len(fuji)} точек, старт {fuji[0][:2]}, финиш {fuji[-1][:2]},"
          f" ele {min(p[2] for p in fuji):.0f}–{max(p[2] for p in fuji):.0f} м")


if __name__ == "__main__":
    main()
