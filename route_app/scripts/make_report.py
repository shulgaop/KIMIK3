#!/usr/bin/env python3
"""make_report.py — отчёт о пройденном походе (по образцу отчётов о категорийных
походах): из записанного трека и свободного описания.

Входные (папка проекта или явные пути):
- записанный GPX с таймстемпами (трек с часов) → разбивка по дням, км,
  набор/сброс, высоты, время в пути — ВСЁ считается кодом;
- описание похода в свободной форме (TXT; PDF/DOCX — через read_program.py):
  блоки «День N …» или с датами раскладываются по дням, остальное — в общие
  заметки;
- дописки (дописки.txt, одна строка = одна заметка; префикс «день N:» —
  к конкретному дню) — можно дополнять и пересобирать отчёт;
- если есть выходные/погода.json в режиме fact — таблица «погода-факт».

Выдача: Отчёт.md + Отчёт.html (офлайн, оглавление, печать A4, профиль высот).

Использование:
  python3 make_report.py projects/<маршрут>
  python3 make_report.py --gpx трек.gpx --text описание.txt --notes дописки.txt \
      --start 2026-09-06 --tz Asia/Dushanbe --out папка --title "Отчёт"
"""
import argparse, importlib.util, json, math, re, sys
from datetime import datetime, timedelta
from pathlib import Path

R = 6371000.0
GPX_NS = "{http://www.topografix.com/GPX/1/1}"


def hav(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def load_recorded_track(gpx_path, tz_hours):
    """Точки трека с временем и высотой → [(local_date, lat, lon, ele, dt_local)]."""
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
        ele_el = el.find(GPX_NS + "ele")
        ele = float(ele_el.text) if ele_el is not None and ele_el.text else 0.0
        dt += timedelta(hours=tz_hours)  # UTC → локальное время похода
        pts.append((dt.date(), float(el.get("lat")), float(el.get("lon")), ele, dt))
    return sorted(pts, key=lambda p: p[4])


def day_stats(pts):
    """Статистика одного дня по его точкам трека."""
    km = sum(hav(*pts[i - 1][1:3], *pts[i][1:3]) for i in range(1, len(pts))) / 1000
    gain = loss = 0.0
    for i in range(1, len(pts)):
        d = pts[i][3] - pts[i - 1][3]
        if d > 0:
            gain += d
        else:
            loss -= d
    eles = [p[3] for p in pts]
    return {"km": round(km, 1), "gain_m": round(gain), "loss_m": round(loss),
            "ele_min": round(min(eles)), "ele_max": round(max(eles)),
            "start": pts[0][4].strftime("%H:%M"), "end": pts[-1][4].strftime("%H:%M")}


def split_days(track):
    """Группировка точек по локальной дате → [(день N, дата, точки)]."""
    days, cur, cur_date = [], [], None
    for p in track:
        if p[0] != cur_date and cur:
            days.append((cur_date, cur))
            cur = []
        cur_date = p[0]
        cur.append(p)
    if cur:
        days.append((cur_date, cur))
    return days


def split_description(text):
    """Описание → {номер дня: текст}; без маркера — в «общие».
    Маркеры: «День 3», «Д3», «03.09», «03.09.2026» в начале абзаца."""
    blocks, day_re = {}, re.compile(
        r"^\s*(?:день\s*\.?\s*(\d{1,2})\b|д\s*\.?\s*(\d{1,2})\b|(\d{1,2})\.(\d{1,2})(?:\.\d{2,4})?)\s*[.:—–-]?\s*",
        re.I)
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        m = day_re.match(para)
        if m and (m.group(1) or m.group(2)):
            day = int(m.group(1) or m.group(2))
        elif m and m.group(3):
            day = ("date", f"{int(m.group(4)):02d}-{int(m.group(3)):02d}")  # мм-дд
        else:
            day = None
        blocks.setdefault(day, []).append(para)
    return blocks


def load_notes(path):
    """Дописки: абзац «день N: …» → к дню; иначе — в общие.
    Абзацы разделяются пустой строкой; внутри абзаца может быть много текста."""
    notes = {}
    if not path or not Path(path).is_file():
        return notes
    text = Path(path).read_text(encoding="utf-8")
    for chunk in re.split(r"\n\s*\n", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.match(r"день\s*(\d{1,2})\s*[:.—-]\s*(.+)", chunk, re.I | re.S)
        notes.setdefault(int(m.group(1)) if m else None,
                         []).append(m.group(2).strip() if m else chunk)
    return notes


def build_report_md(title, days, desc_blocks, notes, weather_fact, track_days):
    """Сборка MD-отчёта: титул, сводка, дни (статистика + события), погода, выводы."""
    L = [f"# {title}", ""]
    total_km = round(sum(s["km"] for _, _, s in days), 1)
    total_gain = sum(s["gain_m"] for _, _, s in days)
    L += ["## Справочные сведения", "",
          f"| Пройдено | {total_km} км (по записанному треку) |",
          f"| Дней в пути | {len(days)} |",
          f"| Суммарный набор | {total_gain} м |",
          f"| Высоты | {min(s['ele_min'] for _, _, s in days)}–"
          f"{max(s['ele_max'] for _, _, s in days)} м |", ""]
    L += ["## Сводная таблица дней", "",
          "| День | Дата | Км | Набор, м | Сброс, м | Высоты, м | В пути |",
          "|---|---|---|---|---|---|---|"]
    for i, (d, _, s) in enumerate(days, 1):
        L.append(f"| {i} | {d} | {s['km']} | {s['gain_m']} | {s['loss_m']} | "
                 f"{s['ele_min']}–{s['ele_max']} | {s['start']}–{s['end']} |")
    L.append("")

    def day_events(i, d):
        out = []
        out += desc_blocks.get(i, [])
        out += desc_blocks.get(("date", d.strftime("%m-%d")), [])
        out += notes.get(i, [])
        return out

    L.append("## Маршрут по дням")
    for i, (d, _, s) in enumerate(days, 1):
        L += ["", f"### День {i} · {d.strftime('%d.%m.%Y')}", "",
              f"**{s['km']} км, +{s['gain_m']} / −{s['loss_m']} м, "
              f"в пути {s['start']}–{s['end']}, высоты {s['ele_min']}–{s['ele_max']} м.**", ""]
        events = day_events(i, d)
        if events:
            L += [e for e in events]
        else:
            L.append("_(события дня не описаны — добавьте через «Дополнить» в модуле Отчёт)_")
    # общие заметки и дописки без дня
    general = desc_blocks.get(None, []) + notes.get(None, [])
    if general:
        L += ["", "## Общие заметки", ""]
        L += general
    if weather_fact:
        L += ["", "## Погода (факт)", "", weather_fact]
    L += ["", "## Выводы", "",
          f"Пройдено {total_km} км за {len(days)} дней, суммарный набор {total_gain} м. "
          "Отчёт собран по записанному треку; статистика дней — расчётная (GPS).", ""]
    return "\n".join(L)


def weather_fact_md(project_out):
    """Таблица фактической погоды из погода.json (режим fact), если есть."""
    p = Path(project_out) / "погода.json"
    if not p.is_file():
        return None
    try:
        w = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if w.get("mode") != "fact":
        return None
    L = ["| Точка | Дата | Ночь | День | Осадки |", "|---|---|---|---|---|"]
    for pt in w.get("points", []):
        for d in pt.get("days", []):
            L.append(f"| {pt['name']} | {d['date']} | {d['tmin']}°C | {d['tmax']}°C | "
                     f"{d['precip_mm']} мм |")
    return "\n".join(L) + f"\n\n_{w['source']}_"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", help="папка проекта (входные/…, выходные/…)")
    ap.add_argument("--gpx", help="записанный трек (по умолчанию входные/трек_с_часов.gpx)")
    ap.add_argument("--text", help="описание похода (по умолчанию входные/описание_похода.txt)")
    ap.add_argument("--notes", help="дописки (по умолчанию входные/дописки.txt)")
    ap.add_argument("--out", help="папка результата (по умолчанию выходные/)")
    ap.add_argument("--title", help="заголовок отчёта")
    ap.add_argument("--tz-offset", type=float, default=5.0,
                    help="сдвиг локального времени похода от UTC, часов (Фаны = +5)")
    args = ap.parse_args()

    if args.project:
        proj = Path(args.project)
        gpx = args.gpx or proj / "входные" / "трек_с_часов.gpx"
        text = args.text or proj / "входные" / "описание_похода.txt"
        notes = args.notes or proj / "входные" / "дописки.txt"
        out = Path(args.out) if args.out else proj / "выходные"
        title = args.title or f"Отчёт о походе · {proj.name}"
        project_out = proj / "выходные"
    else:
        if not args.gpx:
            sys.exit("Без папки проекта укажите --gpx")
        gpx, text, notes = Path(args.gpx), args.text, args.notes
        out = Path(args.out or ".")
        title = args.title or "Отчёт о походе"
        project_out = out

    track = load_recorded_track(gpx, args.tz_offset)
    if not track:
        sys.exit("⚠️  В GPX нет точек с таймстемпами — это не записанный трек с часов. "
                 "Загрузите записанный трек (шаг «Программа» → «Трек с часов»).")
    days = [(d, pts, day_stats(pts)) for d, pts in split_days(track)]

    desc = ""
    if text and Path(text).is_file():
        ext = Path(text).suffix.lower()
        if ext in (".pdf", ".docx"):  # извлечение текста — read_program.py
            spec = importlib.util.spec_from_file_location(
                "read_program", Path(__file__).parent / "read_program.py")
            rp = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(rp)
            desc = rp.extract_text(str(text))
        else:
            desc = Path(text).read_text(encoding="utf-8", errors="replace")
    desc_blocks = split_description(desc) if desc else {}
    notes = load_notes(notes)

    md = build_report_md(title, days, desc_blocks, notes,
                         weather_fact_md(project_out), len(days))
    out.mkdir(parents=True, exist_ok=True)
    (out / "Отчёт.md").write_text(md + "\n", encoding="utf-8")

    # HTML — тем же конвейером, что и гид (оглавление, печать, профиль высот)
    spec = importlib.util.spec_from_file_location(
        "make_guide_html", Path(__file__).parent / "make_guide_html.py")
    gh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gh)
    html = gh.build_html(md, title)
    (out / "Отчёт.html").write_text(html + "\n", encoding="utf-8")

    matched = sum(1 for k in desc_blocks if k is not None)
    print(f"✓ {out / 'Отчёт.html'}: {len(days)} дней, "
          f"блоков описания по дням: {matched}, дописок: {sum(len(v) for v in notes.values())}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
