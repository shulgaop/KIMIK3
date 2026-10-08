#!/usr/bin/env python3
"""photo_marks.py — фотометки: привязка фото и видео к точкам аудиогида.

Каждое фото/видео получает координаты (кодом, не «на глаз»):
- фото — EXIF GPS; видео DJI — время из имени файла (DJI_ГГГГММДДччммсс);
- нет GPS, но есть время и в GPX есть таймстемпы → интерполяция на треке.
Затем файл привязывается к ближайшей точке аудиогида 🎧 (wpt в GPX проекта)
или, если точек 🎧 нет, к ближайшей точке points.json.

Результат:
- фотометки.kml — папки «🎧 Аудиогид» и «📷 Фото по трекам»: каждая фотометка
  с превью <img> (для десктопного Google Earth, фото копируются рядом);
  валидация как в make_kml.py (XML, bbox, styleUrl↔id, без внешних иконок);
- фотометки.json — манифест «аудиотрек → файлы» для гида и отчёта.

Использование:
  python3 photo_marks.py /папка/фото --gpx трек_с_🎧.gpx --out выходные/
  python3 photo_marks.py /папка/фото --points points.json --gpx трек.gpx --out выходные/
"""
import argparse, json, re, shutil, sys
from pathlib import Path

from photo_sort import read_exif, load_track_times, interp_track, haversine  # тот же каталог scripts/
from make_kml import validate as validate_kml

PHOTO_EXT = {".jpg", ".jpeg"}
RE_DJI = re.compile(r"DJI_(\d{14})")  # DJI_20260906095623_001.mp4 → время съёмки

KML_HEADER = ('<?xml version="1.0" encoding="UTF-8"?>\n'
              '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>')
KML_FOOTER = "</Document></kml>"


def xesc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load_audio_points(gpx_path):
    """Точки аудиогида из GPX: wpt с именем «🎧 NN …»."""
    import xml.etree.ElementTree as ET
    NS = "{http://www.topografix.com/GPX/1/1}"
    pts = []
    for el in ET.parse(gpx_path).iter(NS + "wpt"):
        name_el = el.find(NS + "name")
        name = (name_el.text or "").strip()
        if "🎧" not in name:
            continue
        m = re.match(r"🎧\s*(\d+)", name)
        pts.append({"name": name, "track": int(m.group(1)) if m else None,
                    "lat": float(el.get("lat")), "lon": float(el.get("lon"))})
    return pts


def media_datetime(path, exif_dt):
    """Время съёмки: EXIF, для видео DJI — из имени файла."""
    if exif_dt:
        return exif_dt
    m = RE_DJI.search(path.name)
    if m:
        from datetime import datetime
        return datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    return None


def build_kml(audio_pts, marks, photos_dir_name):
    """KML: слой точек аудиогида + фотометки, сгруппированные по трекам."""
    out = [KML_HEADER, "<name>Фотометки аудиогида</name>",
           '<Style id="audio"><IconStyle><color>ff3352db</color></IconStyle></Style>',
           '<Style id="photo"><IconStyle><color>ff00c832</color></IconStyle></Style>']
    out.append("<Folder><name>🎧 Аудиогид</name>")
    for p in audio_pts:
        out.append(f'<Placemark><name>{xesc(p["name"])}</name><styleUrl>#audio</styleUrl>'
                   f'<Point><coordinates>{p["lon"]},{p["lat"]},0</coordinates></Point></Placemark>')
    out.append("</Folder>")
    by_track = {}
    for m in marks:
        by_track.setdefault(m["audio"], []).append(m)
    for audio, items in sorted(by_track.items()):
        out.append(f"<Folder><name>📷 {xesc(audio)}</name>")
        for m in items:
            desc = (f'<![CDATA[<img src="{photos_dir_name}/{xesc(m["stored_as"])}" width="400"><br>'
                    f'{xesc(m["file"])} · {m.get("dt") or "время неизвестно"} · '
                    f'{m["dist_m"]} м до точки аудиогида]]>')
            out.append(f'<Placemark><name>{xesc(m["file"])}</name><styleUrl>#photo</styleUrl>'
                       f'<description>{desc}</description>'
                       f'<Point><coordinates>{m["lon"]},{m["lat"]},0</coordinates></Point></Placemark>')
        out.append("</Folder>")
    out.append(KML_FOOTER)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media", help="папка с фото (JPG) и видео (MP4/MOV, DJI — по имени)")
    ap.add_argument("--gpx", required=True, help="GPX проекта: точки 🎧 и/или трек с таймстемпами")
    ap.add_argument("--track-gpx", help="записанный трек с часов — привязка по времени по нему "
                                        "(иначе используется --gpx)")
    ap.add_argument("--points", help="points.json — запасные цели привязки, если в GPX нет 🎧")
    ap.add_argument("--out", required=True, help="папка результата")
    ap.add_argument("--max-dist", type=float, default=2000.0,
                    help="порог привязки к точке аудиогида, м (дальше — «без привязки»)")
    args = ap.parse_args()

    src = Path(args.media)
    if not src.is_dir():
        sys.exit(f"Нет такой папки: {src}")
    audio_pts = load_audio_points(args.gpx)
    if not audio_pts and args.points:
        audio_pts = [{"name": p["name"], "track": None, "lat": p["lat"], "lon": p["lon"]}
                     for p in json.load(open(args.points, encoding="utf-8"))
                     if "lat" in p and "lon" in p]
    if not audio_pts:
        sys.exit("Нет точек привязки: в GPX нет wpt с 🎧 и points.json не задан/без координат")
    track = load_track_times(args.track_gpx or args.gpx)

    out = Path(args.out)
    photos_dir = out / "фото_метки"
    photos_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(f for f in src.rglob("*")
                   if f.suffix.lower() in PHOTO_EXT or f.suffix.lower() in (".mp4", ".mov"))
    if not files:
        sys.exit("В папке нет фото (JPG) или видео (MP4/MOV)")

    marks, unbound = [], []
    n_gps = n_time = 0
    for f in files:
        ex = read_exif(f) if f.suffix.lower() in PHOTO_EXT else {"lat": None, "lon": None, "dt": None}
        lat, lon = ex["lat"], ex["lon"]
        dt = media_datetime(f, ex["dt"])
        if lat is None and track and dt:
            pos = interp_track(track, dt)
            if pos:
                lat, lon = pos
                n_time += 1
        elif lat is not None:
            n_gps += 1
        if lat is None:
            unbound.append(f.name)
            print(f"⚠️  {f.name}: нет ни GPS, ни времени на треке — без привязки", file=sys.stderr)
            continue
        best, bi = 1e18, 0
        for i, p in enumerate(audio_pts):
            d = haversine(lat, lon, p["lat"], p["lon"])
            if d < best:
                best, bi = d, i
        if best > args.max_dist:
            unbound.append(f.name)
            print(f"⚠️  {f.name}: {round(best)} м до ближайшей точки — без привязки", file=sys.stderr)
            continue
        stored = f"{len(marks):03d}_{f.name}"
        shutil.copy2(f, photos_dir / stored)
        marks.append({"file": f.name, "stored_as": stored,
                      "lat": round(lat, 5), "lon": round(lon, 5),
                      "dt": dt.strftime("%Y-%m-%d %H:%M") if dt else None,
                      "audio": audio_pts[bi]["name"], "track": audio_pts[bi]["track"],
                      "dist_m": round(best)})

    kml_path = out / "фотометки.kml"
    kml_path.write_text(build_kml(audio_pts, marks, "фото_метки") + "\n", encoding="utf-8")
    lats = [p["lat"] for p in audio_pts] + [m["lat"] for m in marks]
    lons = [p["lon"] for p in audio_pts] + [m["lon"] for m in marks]
    margin = 0.05
    validate_kml(str(kml_path), [min(lats) - margin, max(lats) + margin,
                                 min(lons) - margin, max(lons) + margin])

    manifest = {"audio_points": len(audio_pts), "marks": marks, "unbound": unbound}
    (out / "фотометки.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    summary = {"audio_points": len(audio_pts), "bound": len(marks),
               "by_gps": n_gps, "by_time": n_time, "unbound": len(unbound)}
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    print(f"\n✓ {kml_path}: {len(marks)} фотометок к {len(audio_pts)} точкам аудиогида "
          f"(GPS {n_gps}, по времени {n_time}, без привязки {len(unbound)})", file=sys.stderr)


if __name__ == "__main__":
    main()
