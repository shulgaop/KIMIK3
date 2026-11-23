#!/usr/bin/env python3
"""import_audioguide.py — импорт готового аудиогида (mp3) и привязка к точкам 🎧.

Для маршрутов с официальными аудиогидами (напр., Kumano Kodo, Tanabe):
папка с mp3 → каждый файл сопоставляется с точкой аудиогида (wpt «🎧 …»)
в track.gpx по сходству имён (difflib); совпавшие получают номер трека точки,
несовпавшие — честно остаются «без привязки» с ближайшей кандидатурой.

Выдача (в --out): Аудиогид_внешний/<NN — имя>.mp3, аудиогид_импорт.json
(манифест: файл → точка/нет, оценка сходства), Аудиогид_внешний.zip.

Использование:
  python3 import_audioguide.py /папка/mp3 --gpx track.gpx --out выходные/ \
      --min-score 0.45
"""
import argparse, difflib, json, re, shutil, sys, zipfile
from pathlib import Path

from photo_marks import load_audio_points  # точки 🎧 из GPX (тот же каталог scripts/)


def norm(s):
    """Нормализация имени для сопоставления: мелкие буквы, только слова."""
    return re.sub(r"[^a-zа-яё0-9 ]", "", s.lower().replace("_", " ")).strip()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("media", help="папка с mp3 готового аудиогида")
    ap.add_argument("--gpx", required=True, help="track.gpx с точками 🎧")
    ap.add_argument("--out", required=True, help="папка результата")
    ap.add_argument("--min-score", type=float, default=0.45,
                    help="минимальное сходство имени файла и точки (0..1)")
    args = ap.parse_args()

    src = Path(args.media)
    if not src.is_dir():
        sys.exit(f"Нет такой папки: {src}")
    mp3s = sorted(src.rglob("*.mp3"))
    if not mp3s:
        sys.exit("В папке нет mp3")
    audio_pts = load_audio_points(args.gpx)
    if not audio_pts:
        sys.exit("В GPX нет точек 🎧 — сначала разметьте точки аудиогида в track.gpx")

    out = Path(args.out)
    dest_dir = out / "Аудиогид_внешний"
    dest_dir.mkdir(parents=True, exist_ok=True)

    manifest, unbound = [], []
    names = {norm(p["name"]): p for p in audio_pts}
    for f in mp3s:
        base = norm(f.stem)
        best_name, best_score = None, 0.0
        for n in names:
            score = difflib.SequenceMatcher(None, base, n).ratio()
            if score > best_score:
                best_name, best_score = n, score
        if best_name and best_score >= args.min_score:
            p = names[best_name]
            track_no = p.get("track") or 0
            new_name = f"{track_no:02d} — {f.stem}.mp3"
            shutil.copy2(f, dest_dir / new_name)
            manifest.append({"file": f.name, "stored_as": new_name,
                             "audio_point": p["name"], "track": p.get("track"),
                             "score": round(best_score, 2)})
        else:
            unbound.append({"file": f.name, "best_guess": names.get(best_name, {}).get("name"),
                            "score": round(best_score, 2)})
            print(f"⚠️  {f.name}: сходства нет (лучший кандидат "
                  f"{names.get(best_name, {}).get('name')}, {best_score:.2f})", file=sys.stderr)

    zip_path = out / "Аудиогид_внешний.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(dest_dir.glob("*.mp3")):
            z.write(f, f"Аудиогид_внешний/{f.name}")
    (out / "аудиогид_импорт.json").write_text(
        json.dumps({"bound": manifest, "unbound": unbound}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print(f"✓ {zip_path.name}: {len(manifest)} привязано, {len(unbound)} без привязки",
          file=sys.stderr)


if __name__ == "__main__":
    main()
