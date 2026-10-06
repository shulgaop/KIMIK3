#!/usr/bin/env python3
"""gpx_analyze.py — разбор GPX-трека горного маршрута.

Что считает (всё кодом, ничего «на глаз»):
- километраж по гаверсинусу и профиль высот;
- проекцию ключевых точек программы на трек (ближайшая точка -> «км от старта», высота GPS);
- набор/сброс и азимут по плечам между точками;
- градиенты СКОЛЬЗЯЩИМ ОКНОМ 300–500 м (точечные уклоны запрещены — GPS-шум).

Использование:
  python3 gpx_analyze.py track.gpx
  python3 gpx_analyze.py track.gpx --points points.json --window 400

points.json: [{"name": "Кемп Куликалон", "lat": 39.2551, "lon": 68.1723}, ...]
Вывод: JSON-отчёт в stdout (и человекочитаемая сводка в stderr).
"""
import argparse, json, math, sys
import xml.etree.ElementTree as ET

NS = "{http://www.topografix.com/GPX/1/1}"
R = 6371000.0  # радиус Земли, м


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def azimuth(lat1, lon1, lat2, lon2):
    """Истинный азимут из точки 1 в точку 2, градусы 0..360."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def compass(deg):
    rumbs = ["С", "ССВ", "СВ", "ВСВ", "В", "ВЮВ", "ЮВ", "ЮЮВ",
             "Ю", "ЮЮЗ", "ЮЗ", "ЗЮЗ", "З", "ЗСЗ", "СЗ", "ССЗ"]
    return rumbs[round(deg / 22.5) % 16]


def load_gpx(path):
    tree = ET.parse(path)
    trkpts = []
    for el in tree.iter(NS + "trkpt"):
        lat, lon = float(el.get("lat")), float(el.get("lon"))
        ele_el = el.find(NS + "ele")
        ele = float(ele_el.text) if ele_el is not None and ele_el.text else 0.0
        trkpts.append((lat, lon, ele))
    wpts = []
    for el in tree.iter(NS + "wpt"):
        name_el = el.find(NS + "name")
        wpts.append({"name": name_el.text if name_el is not None else "",
                     "lat": float(el.get("lat")), "lon": float(el.get("lon"))})
    return trkpts, wpts


def cumulative(trkpts):
    dist = [0.0]
    for i in range(1, len(trkpts)):
        dist.append(dist[-1] + haversine(*trkpts[i - 1][:2], *trkpts[i][:2]))
    return dist


def project(trkpts, dist, lat, lon):
    """Ближайшая точка трека -> индекс, км от старта, высота, дистанция до неё (м)."""
    best, bi = 1e18, 0
    for i, (la, lo, el) in enumerate(trkpts):
        d = haversine(lat, lon, la, lo)
        if d < best:
            best, bi = d, i
    return {"index": bi, "km": round(dist[bi] / 1000, 2), "ele_gps": round(trkpts[bi][2]),
            "off_track_m": round(best)}


def leg_stats(trkpts, dist, i1, i2):
    """Набор/сброс и азимут плеча между индексами трека."""
    gain = loss = 0.0
    for i in range(i1 + 1, min(i2 + 1, len(trkpts))):
        d = trkpts[i][2] - trkpts[i - 1][2]
        if d > 0:
            gain += d
        else:
            loss -= d
    az = azimuth(*trkpts[i1][:2], *trkpts[i2][:2])
    km = (dist[i2] - dist[i1]) / 1000
    return {"km": round(km, 2), "gain_m": round(gain), "loss_m": round(loss),
            "azimuth_deg": round(az), "azimuth_rumb": compass(az)}


def window_gradients(trkpts, dist, window_m=400.0):
    """Максимальный уклон скользящим окном (метров по треку). Возвращает градусы и где."""
    best_up, best_down, best_pos = 0.0, 0.0, 0.0
    n = len(trkpts)
    j = 0
    for i in range(n):
        while j < n and dist[j] - dist[i] < window_m:
            j += 1
        if j >= n:
            break
        run = dist[j] - dist[i]
        if run < window_m * 0.7:
            continue
        rise = trkpts[j][2] - trkpts[i][2]
        grade = math.degrees(math.atan2(rise, run))
        if grade > best_up:
            best_up = grade
        if grade < best_down:
            best_down = grade
            best_pos = dist[i] / 1000
    return {"max_up_deg": round(best_up, 1), "max_down_deg": round(best_down, 1),
            "steepest_at_km": round(best_pos, 2), "window_m": window_m}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gpx")
    ap.add_argument("--points", help="JSON с ключевыми точками программы")
    ap.add_argument("--window", type=float, default=400.0, help="окно градиентов, м (300–500)")
    args = ap.parse_args()

    trkpts, wpts = load_gpx(args.gpx)
    if len(trkpts) < 2:
        sys.exit("В GPX нет точек трека")
    dist = cumulative(trkpts)

    report = {
        "track_points": len(trkpts),
        "total_km": round(dist[-1] / 1000, 2),
        "ele_min_m": round(min(p[2] for p in trkpts)),
        "ele_max_m": round(max(p[2] for p in trkpts)),
        "waypoints": len(wpts),
        "gradients": window_gradients(trkpts, dist, args.window),
    }

    if args.points:
        pts = json.load(open(args.points, encoding="utf-8"))
        projections = []
        for p in pts:
            pr = project(trkpts, dist, p["lat"], p["lon"])
            projections.append({"name": p["name"], **pr})
            if pr["off_track_m"] > 500:
                print(f"⚠️  «{p['name']}» в {pr['off_track_m']} м от трека — проверить проекцию!",
                      file=sys.stderr)
        legs = []
        for a, b in zip(projections, projections[1:]):
            leg = leg_stats(trkpts, dist, a["index"], b["index"])
            legs.append({"from": a["name"], "to": b["name"], **leg})
        report["projections"] = projections
        report["legs"] = legs

    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print(file=sys.stderr)
    print(f"Итого: {report['total_km']} км, высоты {report['ele_min_m']}–{report['ele_max_m']} м, "
          f"макс. уклоны +{report['gradients']['max_up_deg']}° / {report['gradients']['max_down_deg']}° "
          f"(окно {args.window:.0f} м)", file=sys.stderr)


if __name__ == "__main__":
    main()
