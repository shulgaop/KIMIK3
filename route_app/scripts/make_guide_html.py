#!/usr/bin/env python3
"""make_guide_html.py — офлайн HTML-версия путеводителя из Гид.md.

Один самодостаточный файл (инлайн CSS, системные шрифты, ноль внешних
зависимостей): якорное оглавление, SVG-профиль высот из track.gpx с отметками
точек программы, @media print, мобильная вёрстка. Дизайн — «полевой журнал»
(палитра эталона: бумага #b0c6b3, чернила #111, акцент #db3356).

Использование:
  python3 make_guide_html.py projects/<маршрут>
  python3 make_guide_html.py Гид.md --out Гид.html   # без проекта (без профиля)

Зависимости: pip install markdown
"""
import argparse, importlib.util, json, re, sys
from pathlib import Path

import markdown

CSS = """
:root{--paper:#b0c6b3;--ink:#111;--crim:#db3356;--card:#fdfdfb;--line:#7a947e}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font:16px/1.6 Georgia,serif;margin:0;padding:20px}
.wrap{max-width:820px;margin:0 auto}
h1{font-size:1.7rem;border-bottom:3px solid var(--ink);padding-bottom:8px}
h2{font-size:1.25rem;margin-top:28px;border-bottom:1px solid var(--line);padding-bottom:4px}
h3{font-size:1.05rem;margin-top:20px}
table{border-collapse:collapse;width:100%;margin:12px 0;font-family:-apple-system,"Segoe UI",Roboto,sans-serif;font-size:.88rem}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:var(--ink);color:var(--paper)}
tr:nth-child(even) td{background:rgba(255,255,255,.45)}
code{background:rgba(0,0,0,.08);padding:1px 5px;border-radius:4px;font-size:.9em}
nav{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 18px;margin:16px 0;
     font-family:-apple-system,"Segoe UI",Roboto,sans-serif;font-size:.9rem}
nav a{color:var(--ink);text-decoration:none;display:block;padding:2px 0}
nav a:hover{color:var(--crim)}
nav a.l3{padding-left:18px;font-size:.85rem}
.profile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin:16px 0}
.profile svg{width:100%;height:auto;display:block}
blockquote{border-left:4px solid var(--crim);margin:10px 0;padding:4px 14px;background:rgba(255,255,255,.4)}
html{scroll-behavior:smooth}
@media print{
  body{background:#fff;font-size:12px}
  nav{display:none}
  h2{page-break-before:always}
  table,figure{page-break-inside:avoid}
}
@media (max-width:640px){ body{padding:12px} }
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
             f'<text x="40" y="16" font-size="12" font-family="sans-serif">'
             f'{total_km:.1f} км · {round(emin)}–{round(emax)} м</text>',
             f'<polyline points="{poly}" fill="none" stroke="#111" stroke-width="2"/>',
             f'<polyline points="40,{height-30} {poly} {width-20},{height-30}" '
             f'fill="#7a947e" opacity="0.25" stroke="none"/>']
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
            color = "#db3356" if key else "#111"
            parts.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>'
                         f'<text x="{x}" y="{max(y - 8, 14)}" font-size="10" text-anchor="middle" '
                         f'font-family="sans-serif" fill="{color}">{p["name"]}</text>')
    parts.append(f'<text x="40" y="{height - 8}" font-size="10" font-family="sans-serif">0 км</text>'
                 f'<text x="{width - 20}" y="{height - 8}" font-size="10" text-anchor="end" '
                 f'font-family="sans-serif">{total_km:.0f} км</text>')
    parts.append("</svg>")
    return "\n".join(parts)


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
    args = ap.parse_args()

    src = Path(args.source)
    if src.is_dir():
        md_path = src / "выходные" / "Гид.md"
        gpx = src / "входные" / "track.gpx"
        points = src / "входные" / "points.json"
        out = Path(args.out) if args.out else src / "выходные" / "Гид.html"
        title = f"Путеводитель · {src.name}"
    else:
        md_path = src
        gpx = points = None
        out = Path(args.out) if args.out else src.with_suffix(".html")
        title = src.stem
    if not md_path.is_file():
        sys.exit(f"⚠️  Нет файла {md_path} — сначала сгенерируйте гид (шаг «Гид»)")

    svg = None
    if gpx and gpx.is_file():
        svg = profile_svg(gpx, points)
        print("✓ Профиль высот построен из track.gpx", file=sys.stderr)

    html = build_html(md_path.read_text(encoding="utf-8"), title, svg)
    out.write_text(html + "\n", encoding="utf-8")
    print(f"✓ {out}: {len(html)} символов, офлайн, печать A4", file=sys.stderr)


if __name__ == "__main__":
    main()
