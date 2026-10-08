#!/usr/bin/env python3
"""make_code_guide.py — генератор справочника функций CODE_GUIDE.md.

AST-разбор всех модулей (scripts/*.py + webapp.py): сигнатуры функций,
docstring'и, константы, маршруты FastAPI. Справочник генерируется из кода —
не править руками; перегенерировать после любого изменения кода:

  python3 scripts/make_code_guide.py        # из route_app/

Правило проекта (AGENTS.md, «Стандарты кода»): CODE_GUIDE.md коммитится
в том же коммите, что и изменение кода.
"""
import ast, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
FILES = sorted(BASE.glob("scripts/*.py")) + [BASE / "webapp.py"]
EXCLUDE = {"make_code_guide.py"}  # сам генератор в справочник не входит


def docline(node):
    """Первая строка docstring или тире."""
    return (ast.get_docstring(node) or "—").split("\n")[0]


def consts_of(tree):
    """Имена констант верхнего уровня (SCREAMING_SNAKE)."""
    return [t.id for n in tree.body if isinstance(n, ast.Assign)
            for t in n.targets if isinstance(t, ast.Name) and t.id.isupper()]


def routes_of(tree):
    """Маршруты FastAPI: [(METHOD, path, функция)]."""
    routes = []
    for n in tree.body:
        if not isinstance(n, ast.FunctionDef):
            continue
        for dec in n.decorator_list:
            if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                    and isinstance(dec.func.value, ast.Name) and dec.func.value.id == "app"):
                path = dec.args[0].value if dec.args and isinstance(dec.args[0], ast.Constant) else "?"
                routes.append((dec.func.attr.upper(), path, n.name))
    return routes


def main():
    out = ["# CODE_GUIDE.md — справочник функций",
           "",
           "Генерируется из кода (`python3 scripts/make_code_guide.py` из route_app/) —",
           "не править руками. Обязателен к обновлению в том же коммите, что и код",
           "(AGENTS.md, раздел «Стандарты кода»).",
           ""]
    n_funcs = 0
    for f in FILES:
        if f.name in EXCLUDE:
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        out += [f"## `{f.relative_to(BASE).as_posix()}`", f"_{docline(tree)}_", ""]
        consts = consts_of(tree)
        if consts:
            out.append(f"Константы: `{', '.join(consts)}`\n")
        for method, path, fn in routes_of(tree):
            out.append(f"- `{method} {path}` → `{fn}()`")
            n_funcs += 1
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = ", ".join(a.arg for a in n.args.args)
                prefix = "async " if isinstance(n, ast.AsyncFunctionDef) else ""
                out.append(f"- `{prefix}{n.name}({args})` — {docline(n)}")
                n_funcs += 1
        out.append("")
    (BASE / "CODE_GUIDE.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"✓ CODE_GUIDE.md: {len(FILES) - len(EXCLUDE)} модулей, {n_funcs} функций/маршрутов",
          file=sys.stderr)


if __name__ == "__main__":
    main()
