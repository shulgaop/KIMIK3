#!/usr/bin/env python3
"""make_status.py — снимок проекта СТАТУС_<Маршрут>.md (F9).

Обновляется после КАЖДОГО изменения выдачи (контракт AGENTS.md). Скрипт
сканирует папку проекта и пишет в неё же файл-снимок:

- состав проекта: входные и выходные файлы с размером и датой изменения;
- «Что изменилось с прошлого снимка»: новые / изменённые / удалённые файлы
  (сравнение по sha1 с данными, спрятанными в HTML-комментарии прошлого снимка);
- разделы «Решения, которые НЕ откатывать» и «Открытые вопросы» переносятся
  из прошлого снимка без изменений — их правит человек/агент, не скрипт.

Файл — точка входа для продолжения работы в любой модели: по нему видно,
что уже сделано, что поменялось и какие решения нельзя ломать.

Использование:
  python3 make_status.py projects/Фанские_горы
  python3 make_status.py projects/Фанские_горы --route "Фанские горы — кольцо Чимтарги"

Классификация: файл считается ВЫХОДНЫМ, если в его пути есть папка
«выходные»/«output»/«out»/«выдача», иначе — входным. Сам файл СТАТУС,
.git и __pycache__ игнорируются.
"""
import argparse, hashlib, json, re, sys
from datetime import datetime
from pathlib import Path

OUT_DIRS = {"выходные", "output", "out", "выдача"}
SKIP_DIRS = {".git", "__pycache__"}
MARK_RE = re.compile(r"<!-- routegen-status (\{.*?\}) -->", re.S)


def scan(project):
    """Все файлы проекта: отн. путь -> {size, mtime, sha1}."""
    files = {}
    for p in sorted(project.rglob("*")):
        if not p.is_file() or SKIP_DIRS & set(p.parts):
            continue
        rel = p.relative_to(project).as_posix()
        if rel.startswith("СТАТУС_") and rel.endswith(".md"):
            continue
        data = p.read_bytes()
        files[rel] = {"size": len(data),
                      "mtime": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                      "sha1": hashlib.sha1(data).hexdigest()[:12]}
    return files


def is_output(rel):
    return bool(OUT_DIRS & set(Path(rel).parts[:-1]))


def human_size(n):
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if n < 1024 or unit == "ГБ":
            return f"{n:.0f} {unit}" if unit == "Б" else f"{n:.1f} {unit}".replace(".0 ", " ")
        n /= 1024


def load_prev(status_path):
    """Данные прошлого снимка: файлы + сохраняемые разделы."""
    if not status_path.exists():
        return {}, {}
    text = status_path.read_text(encoding="utf-8")
    m = MARK_RE.search(text)
    files = {}
    if m:
        try:
            files = json.loads(m.group(1)).get("files", {})
        except json.JSONDecodeError:
            print("⚠️  Метка прошлого снимка повреждена — дифф будет «первый снимок»",
                  file=sys.stderr)
    kept = {}
    for title in ("Решения, которые НЕ откатывать", "Открытые вопросы"):
        m = re.search(rf"## {re.escape(title)}\n(.*?)(?=\n## |\n<!-- |\Z)", text, re.S)
        if m and m.group(1).strip():
            kept[title] = m.group(1).strip("\n")
    return files, kept


def diff(prev, cur):
    names = set(prev) | set(cur)
    new = sorted(n for n in names if n not in prev)
    gone = sorted(n for n in names if n not in cur)
    changed = sorted(n for n in names
                     if n in prev and n in cur and prev[n]["sha1"] != cur[n]["sha1"])
    return new, changed, gone


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", help="папка проекта (projects/<маршрут>)")
    ap.add_argument("--route", help="название маршрута (по умолчанию — имя папки)")
    args = ap.parse_args()

    project = Path(args.project)
    if not project.is_dir():
        sys.exit(f"Нет такой папки: {project}")
    route = args.route or project.name
    status_path = project / f"СТАТУС_{project.name}.md"

    cur = scan(project)
    prev, kept = load_prev(status_path)
    new, changed, gone = diff(prev, cur)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    L = [f"# СТАТУС: {route}", "",
         f"Обновлено: {now} (скриптом `make_status.py` — после каждого изменения выдачи).",
         "Файл — точка входа для продолжения работы в любой модели.", "",
         "## Что изменилось с прошлого снимка", ""]
    if not prev:
        L.append("Первый снимок проекта.")
    else:
        for label, names in (("Новые", new), ("Изменённые", changed), ("Удалённые", gone)):
            L.append(f"- **{label}** ({len(names)}): " +
                     (", ".join(f"`{n}`" for n in names) if names else "—"))
    L += ["", f"## Состав проекта ({len(cur)} файлов)", ""]
    for group, pred in (("Входные", lambda r: not is_output(r)),
                        ("Выходные", is_output)):
        rows = [(r, f) for r, f in cur.items() if pred(r)]
        L += [f"### {group} ({len(rows)})", "",
              "| Файл | Размер | Изменён |", "|---|---|---|"]
        L += [f"| `{r}` | {human_size(f['size'])} | {f['mtime']} |" for r, f in rows]
        L.append("")
    L += ["## Решения, которые НЕ откатывать", "",
          kept.get("Решения, которые НЕ откатывать", "_(заполнить при первых решениях)_"), "",
          "## Открытые вопросы", "",
          kept.get("Открытые вопросы", "_(нет)_"), ""]
    marker = json.dumps({"files": cur}, ensure_ascii=False)
    L.append(f"<!-- routegen-status {marker} -->")

    status_path.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"✓ {status_path}: {len(cur)} файлов; новых {len(new)}, "
          f"изменённых {len(changed)}, удалённых {len(gone)}", file=sys.stderr)


if __name__ == "__main__":
    main()
