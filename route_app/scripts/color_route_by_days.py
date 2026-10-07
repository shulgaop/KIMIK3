#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для раскраски маршрута по дням в Google Earth.
Принимает GPX-файл, группирует точки по дням и создаёт KML с разными цветами.

Использование:
    python color_route_by_days.py input.gpx [output.kml]
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from collections import defaultdict
import sys
import os

# Цвета для дней в формате KML (aabbggrr)
DAY_COLORS = [
    "ff0000ff",  # Красный
    "ff00ff00",  # Зелёный
    "ffff0000",  # Синий
    "ff00ffff",  # Жёлтый
    "ffff00ff",  # Пурпурный
    "ffffff00",  # Голубой
    "ff800080",  # Фиолетовый
    "ff008080",  # Оливковый
    "ff808000",  # Сине-зелёный
    "ff800000",  # Тёмно-синий
    "ff000080",  # Тёмно-красный
    "ff008000",  # Тёмно-зелёный
    "ff808080",  # Серый
    "ffffa500",  # Оранжевый
    "ffffc0cb",  # Розовый
]

GPX_NS = "{http://www.topografix.com/GPX/1/1}"
KML_NS = "http://www.opengis.net/kml/2.2"

def parse_gpx(gpx_file):
    """Парсит GPX-файл и возвращает список точек (lat, lon, ele, time)."""
    tree = ET.parse(gpx_file)
    root = tree.getroot()

    # Определяем namespace
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    points = []

    for trk in root.findall(f".//{ns}trk"):
        for trkseg in trk.findall(f"{ns}trkseg"):
            for trkpt in trkseg.findall(f"{ns}trkpt"):
                lat = float(trkpt.get("lat", 0))
                lon = float(trkpt.get("lon", 0))

                ele_elem = trkpt.find(f"{ns}ele")
                ele = float(ele_elem.text) if ele_elem is not None else 0

                time_elem = trkpt.find(f"{ns}time")
                time_str = time_elem.text if time_elem is not None else None

                dt = None
                if time_str:
                    # Пробуем разные форматы
                    for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", 
                                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"]:
                        try:
                            dt = datetime.strptime(time_str.replace("Z", ""), fmt)
                            break
                        except ValueError:
                            continue

                points.append({
                    "lat": lat,
                    "lon": lon,
                    "ele": ele,
                    "time": dt,
                    "time_str": time_str
                })

    return points

def group_by_day(points):
    """Группирует точки по дням."""
    days = defaultdict(list)

    for pt in points:
        if pt["time"]:
            day_key = pt["time"].strftime("%Y-%m-%d")
        else:
            day_key = "unknown"
        days[day_key].append(pt)

    return dict(sorted(days.items()))

def create_kml(days, output_file):
    """Создаёт KML-файл с цветными линиями для каждого дня."""

    # Создаём корневой элемент KML
    kml = ET.Element("kml", xmlns=KML_NS)
    document = ET.SubElement(kml, "Document")

    name = ET.SubElement(document, "name")
    name.text = "Маршрут по дням"

    description = ET.SubElement(document, "description")
    description.text = "Маршрут, раскрашенный по дням"

    # Создаём стили для каждого дня
    day_keys = list(days.keys())
    for i, day in enumerate(day_keys):
        color = DAY_COLORS[i % len(DAY_COLORS)]

        style = ET.SubElement(document, "Style", id=f"style_day_{i}")
        linestyle = ET.SubElement(style, "LineStyle")

        color_elem = ET.SubElement(linestyle, "color")
        color_elem.text = color

        width = ET.SubElement(linestyle, "width")
        width.text = "4"

    # Создаём папку для маршрута
    folder = ET.SubElement(document, "Folder")
    folder_name = ET.SubElement(folder, "name")
    folder_name.text = "Дни маршрута"

    open_folder = ET.SubElement(folder, "open")
    open_folder.text = "1"

    # Создаём Placemark для каждого дня
    for i, day in enumerate(day_keys):
        points = days[day]
        color = DAY_COLORS[i % len(DAY_COLORS)]

        placemark = ET.SubElement(folder, "Placemark")

        pm_name = ET.SubElement(placemark, "name")
        if day == "unknown":
            pm_name.text = "Без даты"
        else:
            # Форматируем дату красиво
            dt = datetime.strptime(day, "%Y-%m-%d")
            pm_name.text = f"День {i+1}: {dt.strftime('%d.%m.%Y')}"

        style_url = ET.SubElement(placemark, "styleUrl")
        style_url.text = f"#style_day_{i}"

        # Создаём LineString
        linestring = ET.SubElement(placemark, "LineString")

        tessellate = ET.SubElement(linestring, "tessellate")
        tessellate.text = "1"

        coordinates = ET.SubElement(linestring, "coordinates")

        # Формируем строку координат
        coords = []
        for pt in points:
            coords.append(f"{pt['lon']},{pt['lat']},{pt['ele']}")

        coordinates.text = " ".join(coords)

    # Записываем в файл
    tree = ET.ElementTree(kml)
    ET.indent(tree, space="  ")
    tree.write(output_file, encoding="utf-8", xml_declaration=True)

    print(f"KML-файл сохранён: {output_file}")
    print(f"Всего дней: {len(days)}")
    for i, day in enumerate(day_keys):
        pt_count = len(days[day])
        color_name = ["Красный", "Зелёный", "Синий", "Жёлтый", "Пурпурный", 
                      "Голубой", "Фиолетовый", "Оливковый", "Сине-зелёный", 
                      "Тёмно-синий", "Тёмно-красный", "Тёмно-зелёный", 
                      "Серый", "Оранжевый", "Розовый"][i % len(DAY_COLORS)]
        if day == "unknown":
            print(f"  Без даты: {pt_count} точек — {color_name}")
        else:
            dt = datetime.strptime(day, "%Y-%m-%d")
            print(f"  День {i+1} ({dt.strftime('%d.%m.%Y')}): {pt_count} точек — {color_name}")

def main():
    if len(sys.argv) < 2:
        print("Использование: python color_route_by_days.py input.gpx [output.kml]")
        print("")
        print("Примеры:")
        print("  python color_route_by_days.py track.gpx")
        print("  python color_route_by_days.py track.gpx colored_track.kml")
        sys.exit(1)

    input_file = sys.argv[1]

    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    else:
        base, _ = os.path.splitext(input_file)
        output_file = base + "_colored.kml"

    if not os.path.exists(input_file):
        print(f"Ошибка: файл не найден: {input_file}")
        sys.exit(1)

    print(f"Читаю GPX: {input_file}")
    points = parse_gpx(input_file)
    print(f"Найдено точек: {len(points)}")

    if not points:
        print("Ошибка: не найдено точек в GPX-файле")
        sys.exit(1)

    days = group_by_day(points)
    print(f"Найдено дней: {len(days)}")

    create_kml(days, output_file)
    print("")
    print("Готово! Откройте файл в Google Earth.")

if __name__ == "__main__":
    main()
