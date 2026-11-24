#!/usr/bin/env python3
"""sources.py — реестр источников проекта SOURCES.md (по протоколу проекта Япония).

Сканирует проект и собирает таблицу:
| ID | Файл или URL | Получен | Проверен | Статус | Что затрагивает | Примечание |

Источники: файлы входных (программа, треки, билеты…) + URL из факты.json
(Википедия/OSM, собранные research.py). Статусы: «учтён» для присутствующих;
ожидаемые документы (билеты, брони) агент добавляет руками со статусом
«ожидается» — скрипт их переносит из прошлого SOURCES.md.

Использование:
  python3 sources.py projects/<маршрут>
"""
import json, sys
from datetime import datetime
from pathlib import Path

IN_DIR, OUT_DIR = "входные", "выходные"
STATUSES = ("ожидается", "получен", "учтён", "конфликтует", "устарел")


def collect(project):
    """Записи реестра: файлы входных + URL источников фактов."""
    project = Path(project)
    rows = []
    in_d = project / IN_DIR
    if in_d.is_dir():
        for f in sorted(in_d.iterdir()):
            if f.is_file():
                rows.append({"what": f"{IN_DIR}/{f.name}",
                             "got": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d"),
                             "status": "учтён", "scope": "маршрут", "note": "файл проекта"})
    facts = project / OUT_DIR / "факты.json"
    if facts.is_file():
        try:
            srcs = json.loads(facts.read_text(encoding="utf-8")).get("sources", [])
        except json.JSONDecodeError:
            srcs = []
        checked = datetime.fromtimestamp(facts.stat().st_mtime).strftime("%Y-%m-%d")
        for url in srcs:
            rows.append({"what": url, "got": checked, "checked": checked,
                         "status": "учтён", "scope": "факты гида", "note": "research.py"})
    return rows


def load_manual(project):
    """Ручные строки прошлого SOURCES.md (статусы «ожидается» и др.) — переносим."""
    p = Path(project) / "SOURCES.md"
    if not p.is_file():
        return []
    keep = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("| S"):  # строка таблицы
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 6 and cells[4] in STATUSES and cells[4] != "учтён":
                keep.append(line)
    return keep


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    project = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    rows = collect(project)
    manual = load_manual(project)

    L = [f"# SOURCES.md — реестр источников · {project.name}", "",
         f"_Обновлён {datetime.now():%Y-%m-%d %H:%M} скриптом sources.py. "
         "Ожидаемые документы (билеты, брони) добавляйте строкой со статусом «ожидается» — "
         "скрипт их переносит при перегенерации._", "",
         "| ID | Файл или URL | Получен | Проверен | Статус | Что затрагивает | Примечание |",
         "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        L.append(f"| S{i:02d} | {r['what']} | {r['got']} | {r.get('checked', r['got'])} | "
                 f"{r['status']} | {r['scope']} | {r['note']} |")
    if manual:
        L.append("")
        L += manual
    out = project / "SOURCES.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"✓ {out}: {len(rows)} источников (+{len(manual)} ручных)", file=sys.stderr)


if __name__ == "__main__":
    main()
