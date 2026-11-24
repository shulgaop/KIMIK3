#!/usr/bin/env python3
"""make_pages_html.py — сборка HTML-страниц гида «Япония 2027» движком main.

Тонкая обёртка над route_app/scripts/make_guide_html.py: общий движок не
изменяется, а заголовки вкладок берутся из данных маршрута — названия дней
из config/days.json («Япония 2027 · <название дня>»), для служебных страниц —
из таблицы PAGES ниже. Для дня вне days.json (ручной Гид.md) заголовок
выводится из первого H1 самого документа.

Использование (из routes/japan/data/):
  python make_pages_html.py
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # routes/japan
ENGINE_PATH = ROOT.parents[1] / "route_app" / "scripts" / "make_guide_html.py"

# Движок лежит вне пакетов, поэтому подключаем его по пути файла.
spec = importlib.util.spec_from_file_location("make_guide_html", ENGINE_PATH)
eng = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eng)

# Служебные страницы верхнего уровня: markdown-источник → заголовок вкладки.
PAGES = {
    "Бронирования.md": "Япония 2027 · Бронирования",
    "Бюджет.md": "Япония 2027 · Бюджет",
    "Источники.md": "Япония 2027 · Источники",
}


def h1_of(md_path):
    """Первый H1 markdown-документа — запасной источник заголовка."""
    m = re.search(r"^#\s+(.+)$", md_path.read_text(encoding="utf-8"), flags=re.M)
    return m.group(1).strip() if m else md_path.stem


def build(source, title, out):
    """Повторяет конвейер main() движка, но с заголовком из данных маршрута."""
    is_slice = source.is_dir()
    md_path = source / "выходные" / "Гид.md" if is_slice else source
    svg = None
    if is_slice:
        gpx = source / "входные" / "track.gpx"
        points = source / "входные" / "points.json"
        if gpx.is_file():
            svg = eng.profile_svg(gpx, points)
    md_text = md_path.read_text(encoding="utf-8")
    if is_slice:
        by_day = eng.photos_by_day(source)
        if by_day:
            md_text, _added = eng.inject_photos(md_text, by_day)
    html = eng.build_html(md_text, title, svg)
    out.write_text(html + "\n", encoding="utf-8")
    print(f"✓ {out.relative_to(ROOT)} — «{title}»", file=sys.stderr)


def main():
    gen = ROOT / "generated"
    days = json.loads((ROOT / "config" / "days.json").read_text(encoding="utf-8"))
    for sl in sorted(gen.glob("slice-day*")):
        num = sl.name.replace("slice-day", "")
        day_title = days.get(num, {}).get("title") or h1_of(sl / "выходные" / "Гид.md")
        build(sl, f"Япония 2027 · {day_title}", sl / "выходные" / "Гид.html")
    for md_name, title in PAGES.items():
        md = gen / md_name
        if md.is_file():
            build(md, title, md.with_suffix(".html"))


if __name__ == "__main__":
    main()
