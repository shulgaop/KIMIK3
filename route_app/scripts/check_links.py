#!/usr/bin/env python3
"""check_links.py — проверка комплекта выдачи перед публикацией.

Сканирует HTML-файлы папки, собирает внутренние ссылки (href/src без схемы)
и проверяет существование целей на диске. Внешние ссылки (http) — опционально
с --http (HEAD-запросы, медленно). Битые ссылки — это блокирующая ошибка
перед публикацией (AGENTS.md, «Обязательная проверка»).

Использование:
  python3 check_links.py выходные/
  python3 check_links.py выходные/ --http
Выход: 0 — всё цело; 1 — есть битые ссылки.
"""
import argparse, re, sys, urllib.parse, urllib.request
from pathlib import Path


def internal_links(folder):
    """Все внутренние ссылки HTML-файлов → абсолютные пути целей."""
    links = {}
    for html in Path(folder).rglob("*.html"):
        text = html.read_text(encoding="utf-8", errors="replace")
        for href in re.findall(r'(?:href|src)="([^"#]+)"', text):
            if href.startswith(("http", "data:", "mailto:")):
                continue
            target = (html.parent / urllib.parse.unquote(href)).resolve()
            links.setdefault(target, []).append(html.name)
    return links


def http_links(folder):
    """Все внешние http(s)-ссылки."""
    found = set()
    for html in Path(folder).rglob("*.html"):
        text = html.read_text(encoding="utf-8", errors="replace")
        found.update(re.findall(r'(?:href|src)="(https?://[^"]+)"', text))
    return sorted(found)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="папка с HTML выдачи")
    ap.add_argument("--http", action="store_true", help="проверять и внешние ссылки (HEAD)")
    args = ap.parse_args()

    links = internal_links(args.folder)
    broken = [(t, srcs) for t, srcs in links.items() if not t.exists()]
    for t, srcs in broken:
        print(f"✗ НЕТ ФАЙЛА: {t}  (из {', '.join(sorted(set(srcs)))})")
    print(f"Внутренних ссылок: {len(links)}; битых: {len(broken)}")

    bad_http = 0
    if args.http:
        urls = http_links(args.folder)
        for url in urls:
            try:
                req = urllib.request.Request(url, method="HEAD",
                                             headers={"User-Agent": "KIMIK3-check/1.0"})
                code = urllib.request.urlopen(req, timeout=10).status
            except Exception as e:
                code = str(e)[:60]
            if code != 200:
                bad_http += 1
                print(f"✗ HTTP {code}: {url}")
        print(f"Внешних проверено: {len(urls)}, битых {bad_http}")

    sys.exit(1 if broken else 0)


if __name__ == "__main__":
    main()
