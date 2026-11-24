#!/usr/bin/env python3
"""make_day_guides.py — генерация дневных срезов гида Японии из конфигурации.

Воспроизводимость (T-006): весь текст — в routes/japan/config/days.json,
все числа (км, наборы, высоты, ходовое время Нейсмита, проекции точек)
вычисляются кодом из GPX; ручных чисел в конфиге нет, кроме официальных
справочных (с пометкой источника).

Для каждого дня создаётся routes/japan/generated/slice-dayN/:
  входные/track.gpx   (если у дня есть трек)
  входные/points.json (если есть точки)
  выходные/Гид.md
Дальше HTML собирается общим движком route_app/scripts/make_guide_html.py.

Использование: python3 make_day_guides.py [номера дней через пробел]
Запускать из routes/japan/data/ (рядом лежат GPX и points_*.json).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "route_app" / "scripts"))
import gpx_analyze as ga  # noqa: E402 — общий движок проекта

ROOT = Path(__file__).resolve().parents[1]          # routes/japan
DATA = ROOT / "data"
GEN = ROOT / "generated"
CONFIG = ROOT / "config" / "days.json"

WALK_MIN_PER_KM = 12      # Нейсмит, как в движке
ASC_MIN_PER_10M = 1       # +1 мин на каждые 10 м набора


def track_stats(gpx_path):
    """Дистанция, набор/сброс, диапазон высот по GPX."""
    trkpts, _ = ga.load_gpx(str(gpx_path))
    dist = ga.cumulative(trkpts)
    total_km = dist[-1] / 1000
    gain = sum(max(0.0, trkpts[i + 1][2] - trkpts[i][2]) for i in range(len(trkpts) - 1))
    loss = sum(max(0.0, trkpts[i][2] - trkpts[i + 1][2]) for i in range(len(trkpts) - 1))
    emin = min(p[2] for p in trkpts)
    emax = max(p[2] for p in trkpts)
    return trkpts, dist, total_km, gain, loss, emin, emax


def naismith_between(trkpts, dist, i0, i1):
    """Ходовое время Нейсмита между индексами трека (минуты)."""
    km = (dist[i1] - dist[i0]) / 1000
    gain = sum(max(0.0, trkpts[i + 1][2] - trkpts[i][2])
               for i in range(i0, i1))
    return km * WALK_MIN_PER_KM + gain / 10 * ASC_MIN_PER_10M


def fmt_hm(minutes):
    """Минуты → '3 ч 53 мин'."""
    m = round(minutes)
    return f"{m // 60} ч {m % 60:02d} мин"


def build_points_table(trkpts, dist, points, start_index=0):
    """Таблица «точка | км | высота | ходом | что смотрим» + суммарное время."""
    rows, total = [], 0.0
    prev_idx = start_index
    for k, p in enumerate(points):
        pr = ga.project(trkpts, dist, p["lat"], p["lon"])
        idx = pr["index"]
        km = dist[idx] / 1000
        leg = 0.0 if k == 0 else naismith_between(trkpts, dist, prev_idx, idx)
        total += leg
        ele = p.get("ele") or round(trkpts[idx][2])
        walk = "старт" if k == 0 else fmt_hm(leg)
        rows.append((p["name"], p.get("jp", ""), km, ele, walk,
                     p.get("note", "")))
        prev_idx = idx
    return rows, total


def render_day(cfg):
    """Markdown гида одного дня по конфигу; возвращает (md, report)."""
    lines = [f"# {cfg['title']}", ""]
    if cfg.get("epigraph"):
        lines += [f"> {cfg['epigraph']}", ""]
    lines.append(f"**Дата:** {cfg['date_human']} · **Формат:** {cfg['format']}")
    lines.append("")

    report = {}
    if cfg.get("track"):
        gpx = DATA / cfg["track"]
        trkpts, dist, km, gain, loss, emin, emax = track_stats(gpx)
        rows, walk_total = build_points_table(
            trkpts, dist, cfg["points_data"])
        report = {"km": km, "gain": gain, "loss": loss,
                  "emin": emin, "emax": emax, "walk_min": walk_total}
        lines += [
            "| Параметр | Значение |", "|---|---|",
            f"| Плечо | {cfg['leg']} |",
            f"| Дистанция | {km:.2f} км (расчёт по GPX, {cfg['track_src']}) |",
            f"| Набор / сброс | +{gain:.0f} м / −{loss:.0f} м |",
            f"| Высоты | {emin:.0f}–{emax:.0f} м |",
            f"| Чистое ходовое время | ~{fmt_hm(walk_total)} (Нейсмит) + привалы ≈ {cfg['with_breaks']} |",
        ]
        for extra in cfg.get("params_extra", []):
            lines.append(f"| {extra[0]} | {extra[1]} |")
        lines += ["", "## План по точкам", ""]
        lines.append("Ходовое время — расчёт Нейсмитом по треку "
                     "(12 мин/км + 1 мин на 10 м набора), без привалов. "
                     "Высоты — SRTM 90 м (S-037).")
        lines += ["", "| Точка | км | Высота | Ходом | Что смотрим |",
                  "|---|---|---|---|---|"]
        for name, jp, pkm, ele, walk, note in rows:
            nm = f"{name} ({jp})" if jp else name
            lines.append(f"| {nm} | {pkm:.1f} | {ele} м | {walk} | {note} |")
        lines.append("")
    elif cfg.get("params_md"):
        lines += cfg["params_md"] + [""]

    for section in cfg.get("sections", []):
        lines.append(f"## {section['h']}")
        lines.append("")
        lines += section["body"] + [""]

    lines += ["---", f"*{cfg['footer']}*"]
    return "\n".join(lines) + "\n", report


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    only = {int(a) for a in sys.argv[1:]} or {int(k) for k in cfg.keys()}
    reports = {}
    for day_s in sorted(cfg, key=int):
        day = int(day_s)
        if day not in only:
            continue
        dc = cfg[day_s]
        if dc.get("points_file"):
            dc["points_data"] = json.loads(
                (DATA / dc["points_file"]).read_text(encoding="utf-8"))
            notes = dc.get("point_notes", {})
            for p in dc["points_data"]:
                if p["name"] in notes:
                    p["note"] = notes[p["name"]]
        out_dir = GEN / f"slice-day{day}"
        (out_dir / "входные").mkdir(parents=True, exist_ok=True)
        (out_dir / "выходные").mkdir(parents=True, exist_ok=True)
        if dc.get("track"):
            src = DATA / dc["track"]
            (out_dir / "входные" / "track.gpx").write_bytes(src.read_bytes())
        if dc.get("points_data"):
            (out_dir / "входные" / "points.json").write_text(
                json.dumps(dc["points_data"], ensure_ascii=False, indent=2),
                encoding="utf-8")
        md, rep = render_day(dc)
        (out_dir / "выходные" / "Гид.md").write_text(md, encoding="utf-8")
        reports[day] = rep
        extra = (f" — {rep['km']:.2f} км, +{rep['gain']:.0f}/−{rep['loss']:.0f} м, "
                 f"ходом {fmt_hm(rep['walk_min'])}") if rep else ""
        print(f"✓ день {day}: Гид.md ({len(md)} символов){extra}")
    print("Готово. Дальше: make_guide_html.py для каждого среза.")


if __name__ == "__main__":
    main()
