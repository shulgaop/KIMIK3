#!/usr/bin/env python3
"""make_guide_html.py — офлайн HTML-версия путеводителя из Гид.md.

Один самодостаточный файл (инлайн CSS, системные шрифты, ноль внешних
зависимостей): якорное оглавление, SVG-профиль высот из track.gpx с отметками
точек программы, @media print, мобильная вёрстка и прокрутка широких таблиц.
Дизайн — современный «полевой журнал»: бумага #f4f1e8, чернила #172820,
тёмно-зелёная оболочка #153b32 и терракотовый акцент #a64f35.

Использование:
  python3 make_guide_html.py projects/<маршрут>
  python3 make_guide_html.py Гид.md --out Гид.html   # без проекта (без профиля)

Зависимости: pip install markdown
"""
import argparse, importlib.util, json, re, sys
from pathlib import Path

import markdown

CSS = """
:root{--paper:#f4f1e8;--ink:#172820;--muted:#617067;--forest:#153b32;
--accent:#a64f35;--crim:#a64f35;--card:#fffdf8;--line:#d4ddd4;--soft:#e8efe7}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:82px}
body{background:var(--paper);color:var(--ink);font:17px/1.7 Georgia,"Times New Roman",serif;margin:0}
body,p,li,td,th{overflow-wrap:anywhere}
a{color:var(--forest);text-underline-offset:3px}
a:focus-visible,button:focus-visible,.table-scroll:focus-visible{outline:3px solid #d57a57;outline-offset:3px}
.site-header{background:var(--forest);color:#fff;border-bottom:3px solid #d2b48c;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.site-header .shell{max-width:1080px;margin:0 auto;padding:13px 24px;display:flex;align-items:center;gap:16px}
.brand{display:flex;align-items:center;gap:10px;color:#fff;text-decoration:none}
.brand:hover{color:#fff}
.brand strong{display:block;font-size:1rem}
.brand small{display:block;color:#cddbd3;font-size:.65rem;letter-spacing:.12em;text-transform:uppercase;margin-top:3px}
.nav-toggle{display:none;margin-left:auto;font:650 .8rem inherit;color:#fff;background:transparent;border:1px solid rgba(255,255,255,.45);border-radius:7px;padding:9px 12px;cursor:pointer}
.wrap{max-width:1080px;margin:0 auto;padding:38px 32px 72px}
h1{font-size:clamp(2rem,5vw,3.4rem);line-height:1.08;letter-spacing:-.025em;margin:0 0 30px;max-width:950px}
h2{font-size:clamp(1.5rem,3vw,2rem);line-height:1.2;margin:48px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--line);scroll-margin-top:80px}
h3{font:700 1.08rem/1.4 -apple-system,"Segoe UI",sans-serif;color:var(--forest);margin:28px 0 10px}
p,ul,ol{max-width:76ch}
ul,ol{padding-left:24px}
li{margin:5px 0}
.table-scroll{max-width:100%;overflow-x:auto;margin:18px 0;border:1px solid var(--line);border-radius:10px;background:var(--card)}
table{border-collapse:collapse;width:100%;min-width:680px;margin:0;font-family:-apple-system,"Segoe UI",Roboto,sans-serif;font-size:.86rem;background:var(--card)}
th,td{padding:11px 13px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}
th{background:var(--soft);color:var(--forest);font-size:.7rem;text-transform:uppercase;letter-spacing:.05em}
tr:last-child td{border-bottom:0}
code{background:var(--soft);padding:1px 5px;border-radius:4px;font-size:.9em}
pre{max-width:100%;overflow:auto;background:var(--soft);padding:14px;border-radius:8px}
pre code{background:transparent;padding:0}
nav.toc{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 22px;margin:24px 0;columns:2;column-gap:34px;font-family:-apple-system,"Segoe UI",Roboto,sans-serif;font-size:.88rem}
.toc-title{display:block;column-span:all;font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:8px}
nav.toc a{color:var(--ink);text-decoration:none;display:block;padding:7px 0;border-bottom:1px solid var(--line);break-inside:avoid}
nav.toc a:hover{color:var(--accent)}
nav.toc a.l3{padding-left:18px;font-size:.82rem;color:var(--muted)}
.profile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin:22px 0;break-inside:avoid}
.profile svg{width:100%;height:auto;display:block}
blockquote{border-left:4px solid var(--accent);margin:18px 0;padding:12px 16px;background:var(--card);border-radius:0 8px 8px 0}
.photos{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin:16px 0}
.photos img{width:100%;height:150px;object-fit:cover;border-radius:8px;border:1px solid var(--line);cursor:zoom-in}
@media (max-width:700px){
  .site-header .shell{padding:11px 16px}
  .nav-toggle{display:block;min-height:42px}
  .wrap{padding:28px 18px 56px}
  nav.toc{display:none;columns:1;padding:15px 18px}
  nav.toc.open{display:block}
  h2{margin-top:38px}
  .photos{grid-template-columns:repeat(2,minmax(0,1fr))}
  .photos img{height:130px}
}
@media (pointer:coarse){.nav-toggle,nav.toc a{min-height:44px}.nav-toggle{font-size:16px}nav.toc a{display:flex;align-items:center}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media print{
  body{background:#fff;font-size:11pt}
  .site-header,nav.toc{display:none!important}
  .wrap{max-width:none;padding:0}
  h1{font-size:24pt}
  h2{break-after:avoid}
  h3{break-after:avoid}
  .table-scroll{overflow:visible;border-color:#999}
  table{min-width:0}
  th,td{padding:6px 8px}
  table,figure,.profile{break-inside:avoid}
  .photos img{height:80px}
}
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
             f'<polyline points="{poly}" fill="none" stroke="#172820" stroke-width="2"/>',
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
            color = "#a64f35" if key else "#172820"
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
    """Собрать автономный HTML: заголовок, содержание, профиль, текст и таблицы.

    Возвращает строку HTML без внешних ресурсов. Широкие таблицы помещаются
    в собственные прокручиваемые области, на телефоне содержание раскрывается
    кнопкой; скрипт меню и стили встроены в документ.
    """
    body = markdown.markdown(md_text, extensions=["tables", "toc", "fenced_code"],
                             extension_configs={"toc": {"slugify": lambda v, s: re.sub(r"\s+", "-", v.strip())}})
    body = re.sub(r"<table>.*?</table>",
                  lambda m: '<div class="table-scroll" role="region" tabindex="0" '
                            f'aria-label="Таблица с горизонтальной прокруткой">{m.group(0)}</div>',
                  body, flags=re.S)
    nav = ['<nav class="toc" id="guideNav" aria-label="Содержание"><b class="toc-title">Содержание</b>']
    for m in re.finditer(r'<h([23]) id="([^"]+)">(.+?)</h\1>', body):
        lvl, anchor, text = m.groups()
        text = re.sub(r"<[^>]+>", "", text)
        nav.append(f'<a href="#{anchor}" class="l{lvl}">{text}</a>')
    nav.append("</nav>")
    profile = f'<div class="profile">{svg}</div>' if svg else ""
    heading = re.search(r"<h1\b.*?</h1>", body, flags=re.S)
    lead = heading.group(0) if heading else ""
    content = body[heading.end():] if heading else body
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#153b32">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>
<header class="site-header"><div class="shell">
  <a class="brand" href="#top"><span><strong>Trek Fourge</strong><small>Полевой путеводитель</small></span></a>
  <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="guideNav">Содержание</button>
</div></header>
<main class="wrap" id="top">
{lead}
{"".join(nav)}
{profile}
{content}
</main>
<script>
(() => {{
  const toggle = document.querySelector('.nav-toggle');
  const nav = document.getElementById('guideNav');
  const close = () => {{ nav.classList.remove('open'); toggle.setAttribute('aria-expanded', 'false'); }};
  toggle.addEventListener('click', () => {{
    const open = nav.classList.toggle('open'); toggle.setAttribute('aria-expanded', String(open));
  }});
  nav.addEventListener('click', event => {{ if(event.target.closest('a')) close(); }});
  document.addEventListener('keydown', event => {{ if(event.key === 'Escape') {{ close(); toggle.focus(); }} }});
}})();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="папка проекта или путь к Гид.md")
    ap.add_argument("--out", help="выходной HTML (по умолчанию выходные/Гид.html)")
    ap.add_argument("--no-photos", action="store_true",
                    help="не вставлять фото дней (по умолчанию — из фото_карта.json/фотометки.json)")
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
