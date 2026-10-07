#!/usr/bin/env python3
"""photo_sort.py — сортировка фотографий похода по точкам и дням маршрута.

Для каждого фото (JPG/JPEG) читается EXIF (Pillow): GPS-координаты и время
съёмки. Привязка — ТОЛЬКО вычислениями, ничего «на глаз»:
- есть GPS → ближайшая точка маршрута (гаверсинус из gpx_analyze.py); дальше
  --max-dist м от неё — фото попадает в группу «мимо маршрута»;
- GPS нет, но есть время и в GPX есть таймстемпы → позиция на треке
  интерполируется по времени;
- день похода — по дате съёмки относительно --start (день 1 = день старта);
- без EXIF вовсе — группа «неразобранное» (честно, без выдумок).

Результат в папке --out:
- фото/День_N_<точка>/… — копии фото, рассортированные по папкам;
- фотоотчёт.html — офлайн-отчёт: разделы по дням/точкам, сетка фото, печать;
- фото_карта.json — манифест привязки каждого файла (для других модулей).

Использование:
  python3 photo_sort.py /путь/к/фото --points points.json --start 2026-09-06 \
      --out выходные/ --gpx track.gpx --max-dist 1000
"""
import argparse, json, math, re, shutil, sys
from datetime import datetime, date
from pathlib import Path

R = 6371000.0  # радиус Земли, м
GPX_NS = "{http://www.topografix.com/GPX/1/1}"
PHOTO_EXT = {".jpg", ".jpeg"}


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def read_exif(path):
    """GPS и время съёмки из EXIF. Возвращает {lat, lon, dt} с None-полями."""
    from PIL import Image
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            gps = exif.get_ifd(0x8825)  # GPS IFD
            dt_raw = exif.get_ifd(0x8769).get(36867) or exif.get(306)  # DateTimeOriginal | DateTime
    except Exception as e:
        print(f"⚠️  {path.name}: EXIF не читается ({e})", file=sys.stderr)
        return {"lat": None, "lon": None, "dt": None}

    lat = lon = None
    if gps and 2 in gps and 4 in gps:  # GPSLatitude + GPSLongitude
        def to_deg(v):
            return float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
        lat = to_deg(gps[2]) * (1 if gps.get(1, "N") == "N" else -1)
        lon = to_deg(gps[4]) * (1 if gps.get(3, "E") == "E" else -1)
    dt = None
    if dt_raw:
        try:
            dt = datetime.strptime(str(dt_raw).strip(), "%Y:%m:%d %H:%M:%S")
        except ValueError:
            pass
    return {"lat": lat, "lon": lon, "dt": dt}


def load_track_times(gpx_path):
    """Точки трека с таймстемпами: [(datetime, lat, lon)], по времени."""
    import xml.etree.ElementTree as ET
    pts = []
    for el in ET.parse(gpx_path).iter(GPX_NS + "trkpt"):
        t = el.find(GPX_NS + "time")
        if t is None or not t.text:
            continue
        try:
            dt = datetime.fromisoformat(t.text.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            continue
        pts.append((dt, float(el.get("lat")), float(el.get("lon"))))
    return sorted(pts)


def interp_track(track, dt):
    """Позиция на треке в момент dt (интерполяция между соседними точками)."""
    if not track or dt is None:
        return None
    if dt <= track[0][0]:
        return track[0][1], track[0][2]
    if dt >= track[-1][0]:
        return track[-1][1], track[-1][2]
    for (t1, la1, lo1), (t2, la2, lo2) in zip(track, track[1:]):
        if t1 <= dt <= t2:
            k = (dt - t1).total_seconds() / max((t2 - t1).total_seconds(), 1)
            return la1 + (la2 - la1) * k, lo1 + (lo2 - lo1) * k
    return None


def nearest_point(points, lat, lon):
    """Ближайшая точка маршрута: (индекс, дистанция м)."""
    best, bi = 1e18, 0
    for i, p in enumerate(points):
        if "lat" not in p or "lon" not in p:
            continue
        d = haversine(lat, lon, p["lat"], p["lon"])
        if d < best:
            best, bi = d, i
    return bi, best


def day_number(dt, start):
    """День похода по дате съёмки (день 1 = дата старта); None, если вне дат."""
    if dt is None or start is None:
        return None
    return (dt.date() - start).days + 1


def build_html(report, title):
    """Офлайн HTML-отчёт: разделы по группам, сетка фото, печать A4."""
    css = """
  body{background:#b0c6b3;color:#111;font:15px/1.5 -apple-system,"Segoe UI",Roboto,sans-serif;padding:18px}
  .wrap{max-width:900px;margin:0 auto}
  h1{font-family:Georgia,serif;font-size:1.6rem}
  h2{font-family:Georgia,serif;font-size:1.1rem;margin:16px 0 8px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
  figure{margin:0;background:#fdfdfb;border:1px solid #7a947e;border-radius:6px;padding:6px}
  figure img{width:100%;border-radius:4px;display:block}
  figcaption{font-size:.75rem;word-break:break-all}
  .meta{font-size:.85rem;opacity:.8}
  @media print{body{background:#fff}figure{break-inside:avoid}}
"""
    parts = [f"<!DOCTYPE html><html lang='ru'><head><meta charset='UTF-8'>",
             f"<meta name='viewport' content='width=device-width, initial-scale=1'>",
             f"<title>{title}</title><style>{css}</style></head><body><div class='wrap'>",
             f"<h1>{title}</h1>",
             f"<p class='meta'>Фото: {report['total']} · с GPS: {report['with_gps']} · "
             f"по времени трека: {report['by_time']} · неразобранных: {report['unsorted']} · "
             f"собрано {report['generated_at']}</p>"]
    for g in report["groups"]:
        parts.append(f"<h2>{g['title']} ({len(g['photos'])})</h2><div class='grid'>")
        for ph in g["photos"]:
            parts.append(f"<figure><img src='{ph['rel']}' loading='lazy'>"
                         f"<figcaption>{ph['file']}"
                         + (f"<br>{ph['dt']}" if ph.get("dt") else "")
                         + (f"<br>{ph['dist_m']} м от точки" if ph.get("dist_m") else "")
                         + "</figcaption></figure>")
        parts.append("</div>")
    parts.append("</div></body></html>")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photos", help="папка с фотографиями (JPG)")
    ap.add_argument("--points", required=True, help="points.json маршрута (name/lat/lon)")
    ap.add_argument("--gpx", help="трек с таймстемпами — привязка фото без GPS по времени")
    ap.add_argument("--start", help="первый день похода ГГГГ-ММ-ДД — нумерация дней")
    ap.add_argument("--out", required=True, help="папка результата (фото/, фотоотчёт.html)")
    ap.add_argument("--max-dist", type=float, default=1000.0,
                    help="порог привязки к точке, м (дальше — «мимо маршрута»)")
    args = ap.parse_args()

    src = Path(args.photos)
    if not src.is_dir():
        sys.exit(f"Нет такой папки: {src}")
    points = json.load(open(args.points, encoding="utf-8"))
    points_xy = [p for p in points if "lat" in p and "lon" in p]
    if not points_xy:
        sys.exit("В points.json нет точек с координатами — привязка невозможна")
    start = date.fromisoformat(args.start) if args.start else None
    track = load_track_times(args.gpx) if args.gpx else []
    out = Path(args.out)
    photos_out = out / "фото"
    photos_out.mkdir(parents=True, exist_ok=True)

    files = sorted(f for f in src.rglob("*") if f.suffix.lower() in PHOTO_EXT)
    if not files:
        sys.exit("В папке нет JPG-фотографий")

    groups = {}   # ключ группы -> {"title":..., "photos":[...]}
    manifest = []
    n_gps = n_time = n_unsorted = 0

    for f in files:
        ex = read_exif(f)
        lat, lon, dt = ex["lat"], ex["lon"], ex["dt"]
        how = None
        if lat is not None:
            how = "gps"
        elif track:
            pos = interp_track(track, dt)
            if pos:
                lat, lon = pos
                how = "time"

        rec = {"file": f.name, "dt": dt.strftime("%Y-%m-%d %H:%M") if dt else None,
               "how": how}
        day = day_number(dt, start)
        if how:
            i, dist = nearest_point(points_xy, lat, lon)
            rec.update(lat=round(lat, 5), lon=round(lon, 5),
                       point=points_xy[i]["name"], dist_m=round(dist))
            if dist <= args.max_dist:
                title = (f"День {day} · " if day else "") + points_xy[i]["name"]
                key = (day or 999, points_xy[i]["name"])
            else:
                title, key = "Мимо маршрута", (1000, "Мимо маршрута")
            if how == "gps":
                n_gps += 1
            else:
                n_time += 1
        else:
            title, key = "Неразобранное (нет EXIF)", (1001, "Неразобранное")
            n_unsorted += 1
        rec["group"] = title

        dest_dir = photos_out / re.sub(r'[\\/:*?"<>|]', "_", title)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f.name
        if dest.exists():
            dest = dest_dir / f"{f.stem}_{len(list(dest_dir.glob(f.stem + '*')))}{f.suffix}"
        shutil.copy2(f, dest)
        rec["rel"] = dest.relative_to(out).as_posix()

        groups.setdefault(key, {"title": title, "photos": []})["photos"].append(rec)
        manifest.append(rec)

    ordered = [groups[k] for k in sorted(groups)]
    report = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
              "total": len(files), "with_gps": n_gps, "by_time": n_time,
              "unsorted": n_unsorted, "groups": ordered}
    (out / "фото_карта.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    title = "Фотоотчёт по маршруту"
    (out / "фотоотчёт.html").write_text(build_html(report, title) + "\n", encoding="utf-8")

    json.dump({k: v for k, v in report.items() if k != "groups"} |
              {"groups": [{"title": g["title"], "count": len(g["photos"])} for g in ordered]},
              sys.stdout, ensure_ascii=False, indent=2)
    print(f"\n✓ {out / 'фотоотчёт.html'}: {len(files)} фото → {len(ordered)} групп "
          f"(GPS {n_gps}, по времени {n_time}, неразобранных {n_unsorted})", file=sys.stderr)


if __name__ == "__main__":
    main()
