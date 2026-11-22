#!/usr/bin/env python3
"""make_guide_html.py — офлайн HTML-версия путеводителя из Гид.md.

Один самодостаточный файл (инлайн CSS, системные шрифты, ноль внешних
зависимостей): якорное оглавление, SVG-профиль высот из track.gpx с отметками
точек программы, @media print, мобильная вёрстка. Дизайн — «полевой журнал»
в японской палитре: бумага васи #f4efe3, чернила #1c1a16, индиго ай #1f3a5f,
акцент — вермильон тории #b23a2a (≤10% площади).

Использование:
  python3 make_guide_html.py projects/<маршрут>
  python3 make_guide_html.py projects/<маршрут> --title "Япония 2027 · День 6"
  python3 make_guide_html.py Гид.md --out Гид.html   # без проекта (без профиля)

Зависимости: pip install markdown
"""
import argparse, importlib.util, json, re, sys
from pathlib import Path

import markdown

CSS = """
:root{--paper:#f4efe3;--ink:#1c1a16;--ai:#1f3a5f;--shu:#b23a2a;--card:#fcfbf6;--line:#c9c0a8}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font:16px/1.65 Georgia,"Times New Roman",serif;margin:0;padding:24px 20px}
.wrap{max-width:820px;margin:0 auto}
h1{font-size:1.75rem;line-height:1.25;color:var(--ai);border-bottom:3px double var(--ai);padding-bottom:10px;margin:8px 0 20px}
h2{font-size:1.22rem;margin-top:36px;border-left:5px solid var(--shu);padding:2px 0 2px 12px;
   background:linear-gradient(to right,rgba(31,58,95,.06),transparent)}
h3{font-size:1.05rem;margin-top:24px;color:var(--ai)}
a{color:var(--ai)}
a:hover{color:var(--shu)}
table{border-collapse:collapse;width:100%;margin:16px 0;background:var(--card);
      font-family:-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;font-size:.88rem}
th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
th{background:var(--ai);color:#f8f5ec;font-weight:600}
tr:nth-child(even) td{background:rgba(31,58,95,.045)}
code{background:rgba(31,58,95,.09);padding:1px 5px;border-radius:4px;font-size:.9em}
nav{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 20px;margin:16px 0 24px;
    box-shadow:0 1px 3px rgba(28,26,22,.08);
    font-family:-apple-system,"Segoe UI",Roboto,sans-serif;font-size:.9rem}
nav b{color:var(--ai);letter-spacing:.04em}
nav a{color:var(--ink);text-decoration:none;display:block;padding:3px 0;border-bottom:1px dotted var(--line)}
nav a:last-child{border-bottom:none}
nav a:hover{color:var(--shu)}
nav a.l3{padding-left:20px;font-size:.85rem}
.profile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:16px 0;
         box-shadow:0 1px 3px rgba(28,26,22,.08)}
.profile svg{width:100%;height:auto;display:block}
blockquote{border-left:4px solid var(--shu);margin:16px 0;padding:8px 16px;
           background:rgba(178,58,42,.06);border-radius:0 8px 8px 0}
.photos{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
.photos img{height:110px;border-radius:8px;border:1px solid var(--line);cursor:zoom-in}
.photos img:active{position:fixed;inset:5%;height:auto;max-width:90%;z-index:9;background:#fff}
@media print{.photos img{height:60px}}
html{scroll-behavior:smooth}
@media print{
  body{background:#fff;font-size:12px}
  nav{display:none}
  h2{page-break-before:always;background:none}
  table,figure{page-break-inside:avoid}
}
@media (max-width:640px){ body{padding:14px 12px}
  h1{font-size:1.4rem}
  table{display:block;overflow-x:auto} }
"""


def load_gpx_analyze():
    spec = importlib.util.spec_from_file_location(
        "gpx_analyze", Path(__file__).parent / "gpx_analyze.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def profile_svg(gpx_path, points_path, width=760, height=220):
    """SVG-профиль высот: линия трека + точки программы с подписями."""
    ga = load_gpx_analyze()
    trkpts, _ = ga.load_gpx(str(gpx_path))
    dist = ga.cumulative(trkpts)
    n = len(trkpts)
    step = max(1, n // 240)  # прореживание до ~240 точек
    idx = list(range(0, n, step))
    emin = min(trkpts[i][2] for i in idx)
    emax = max(trkpts[i][2] for i in idx)
    span = max(emax - emin, 1)
    total_km = dist[-1] / 1000

    def xy(i):
        x = 40 + (dist[i] / dist[-1]) * (width - 60)
        y = height - 30 - ((trkpts[i][2] - emin) / span) * (height - 60)
        return round(x, 1), round(y, 1)

    poly = " ".join(f"{x},{y}" for x, y in (xy(i) for i in idx))
    parts = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
             f'role="img" aria-label="Профиль высот">',
             f'<text x="40" y="16" font-size="12" font-family="sans-serif" fill="#1f3a5f">'
             f'{total_km:.1f} км · {round(emin)}–{round(emax)} м</text>',
             f'<polyline points="{poly}" fill="none" stroke="#1c1a16" stroke-width="2"/>',
             f'<polyline points="40,{height-30} {poly} {width-20},{height-30}" '
             f'fill="#1f3a5f" opacity="0.18" stroke="none"/>']
    if points_path and Path(points_path).is_file():
        pts = json.load(open(points_path, encoding="utf-8"))
        ele_top = max((p.get("ele") or 0) for p in pts)  # ключевая точка — самая высокая
        for p in pts:
            if "lat" not in p:
                continue
            pr = ga.project(trkpts, dist, p["lat"], p["lon"])
            if pr["off_track_m"] > 1500:
                continue
            x, y = xy(pr["index"])
            key = bool(ele_top) and p.get("ele") == ele_top
            color = "#b23a2a" if key else "#1c1a16"
            parts.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>'
                         f'<text x="{x}" y="{max(y - 8, 14)}" font-size="10" text-anchor="middle" '
                         f'font-family="sans-serif" fill="{color}">{p["name"]}</text>')
    parts.append(f'<text x="40" y="{height - 8}" font-size="10" font-family="sans-serif">0 км</text>'
                 f'<text x="{width - 20}" y="{height - 8}" font-size="10" text-anchor="end" '
                 f'font-family="sans-serif">{total_km:.0f} км</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def photos_by_day(project):
    """Фото по дням из выходные/фото_карта.json (photo_sort) и фотометки.json
    (photo_marks, имена 🎧 с «День N»). Возвращает {номер_дня: [отн. пути]}."""
    out = Path(project) / "выходные"
    by_day = {}
    card = out / "фото_карта.json"
    if card.is_file():
        for rec in json.loads(card.read_text(encoding="utf-8")):
            m = re.match(r"День (\d+)", rec.get("group") or "")
            if m and rec.get("rel"):
                by_day.setdefault(int(m.group(1)), []).append(rec["rel"])
    marks = out / "фотометки.json"
    if marks.is_file():
        for rec in json.loads(marks.read_text(encoding="utf-8")).get("marks", []):
            m = re.search(r"День (\d+)", rec.get("audio") or "")
            if m:
                by_day.setdefault(int(m.group(1)), []).append(f"фото_метки/{rec['stored_as']}")
    return by_day


def inject_photos(md_text, by_day):
    """После заголовков «##/### День N …» вставить ряд превью фото дня (raw HTML)."""
    if not by_day:
        return md_text, 0
    lines, added = md_text.split("\n"), 0
    out = []
    for ln in lines:
        out.append(ln)
        m = re.match(r"^#{2,3}\s*(?:День|Дни)\s+(\d+)", ln)
        if m and int(m.group(1)) in by_day:
            imgs = "".join(f"<img src='{p}' loading='lazy'>" for p in by_day[int(m.group(1))])
            out.append(f"\n<div class='photos'>{imgs}</div>\n")
            added += len(by_day[int(m.group(1))])
    return "\n".join(out), added


def build_html(md_text, title, svg=None):
    body = markdown.markdown(md_text, extensions=["tables", "toc", "fenced_code"],
                             extension_configs={"toc": {"slugify": lambda v, s: re.sub(r"\s+", "-", v.strip())}})
    # оглавление из заголовков h2/h3
    nav = ['<nav><b>Содержание</b>']
    for m in re.finditer(r'<h([23]) id="([^"]+)">(.+?)</h\1>', body):
        lvl, anchor, text = m.groups()
        text = re.sub(r"<[^>]+>", "", text)
        nav.append(f'<a href="#{anchor}" class="l{lvl}">{text}</a>')
    nav.append("</nav>")
    profile = f'<div class="profile">{svg}</div>' if svg else ""
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
{"".join(nav)}
{profile}
{body}
</div>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="папка проекта или путь к Гид.md")
    ap.add_argument("--out", help="выходной HTML (по умолчанию выходные/Гид.html)")
    ap.add_argument("--title", help="заголовок страницы (по умолчанию — имя проекта/файла)")
    ap.add_argument("--no-photos", action="store_true",
                    help="не вставлять фото дней (по умолчанию — из фото_карта.json/фотометки.json)")
    args = ap.parse_args()

    src = Path(args.source)
    if src.is_dir():
        md_path = src / "выходные" / "Гид.md"
        gpx = src / "входные" / "track.gpx"
        points = src / "входные" / "points.json"
        out = Path(args.out) if args.out else src / "выходные" / "Гид.html"
        title = args.title or f"Путеводитель · {src.name}"
    else:
        md_path = src
        gpx = points = None
        out = Path(args.out) if args.out else src.with_suffix(".html")
        title = args.title or src.stem
    if not md_path.is_file():
        sys.exit(f"⚠️  Нет файла {md_path} — сначала сгенерируйте гид (шаг «Гид»)")

    svg = None
    if gpx and gpx.is_file():
        svg = profile_svg(gpx, points)
        print("✓ Профиль высот построен из track.gpx", file=sys.stderr)

    md_text = md_path.read_text(encoding="utf-8")
    if src.is_dir() and not args.no_photos:
        by_day = photos_by_day(src)
        if by_day:
            md_text, added = inject_photos(md_text, by_day)
            print(f"✓ Фото в днях: {added} шт. в {len(by_day)} днях", file=sys.stderr)
    html = build_html(md_text, title, svg)
    out.write_text(html + "\n", encoding="utf-8")
    print(f"✓ {out}: {len(html)} символов, офлайн, печать A4", file=sys.stderr)


if __name__ == "__main__":
    main()
