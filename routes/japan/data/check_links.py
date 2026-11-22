"""Разовая проверка комплекта перед публикацией (T-007).

Сканирует все HTML в generated/, собирает внутренние ссылки (href/src без
схемы) и проверяет: существование цели на диске и HTTP 200 через локальный
сервер на 127.0.0.1:8123 (должен быть уже запущен).
"""
import pathlib
import re
import urllib.parse
import urllib.request

КОРЕНЬ = pathlib.Path(__file__).resolve().parent.parent / "generated"

ссылки: set[pathlib.Path] = set()
for html in КОРЕНЬ.rglob("*.html"):
    текст = html.read_text(encoding="utf-8")
    for href in re.findall(r'(?:href|src)="([^"#]+)"', текст):
        if href.startswith(("http", "data:", "mailto:")):
            continue
        ссылки.add((html.parent / urllib.parse.unquote(href)).resolve())

битые = [с for с in sorted(ссылки) if not с.exists()]
print(f"внутренних ссылок: {len(ссылки)}; отсутствуют на диске: {len(битые)}")
for б in битые:
    print("  НЕТ ФАЙЛА:", б.relative_to(КОРЕНЬ))

плохие = []
for с in sorted(ссылки):
    if not с.exists():
        continue
    отн = с.relative_to(КОРЕНЬ).as_posix()
    url = "http://127.0.0.1:8123/" + urllib.parse.quote(отн)
    try:
        код = urllib.request.urlopen(url).status
    except Exception as ошибка:  # noqa: BLE001 — сводная проверка, детали ниже
        код = repr(ошибка)
    if код != 200:
        плохие.append((отн, код))
print(f"HTTP-проверка: плохих {len(плохие)}")
for отн, код in плохие:
    print("  ", отн, "->", код)
