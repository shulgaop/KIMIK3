#!/usr/bin/env python3
"""project-atlas: persistent project memory for agent work on large corpora.

Deterministic, LLM-free index of a project folder: file inventory with content
hashes, per-file outlines (headings, paragraph/table counts, part numbers,
keywords), keyword-based file clusters, and resumable batch-job manifests.

Subcommands:
  build [root]                 build atlas-out/atlas.json + ATLAS.md
  update [root]                re-extract only new/changed/deleted files
  query <text> [root]          find files by keyword / part number / heading
  related <file> [root]        files sharing keywords with <file>
  manifest <job> <dir|files..> create a resumable batch-job manifest
  status <job>                 show batch progress (pending/done/failed)
  done <job> <file> [note]     mark a file processed
  fail <job> <file> <reason>   mark a file failed

Only Python 3.9+ stdlib. Optional: pypdf (richer PDF outlines).
В Git-проекте индексируются tracked и неигнорируемые untracked-файлы;
.gitignore — обязательная граница приватности и исключения выходных данных.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

OUT_DIR = "atlas-out"
ATLAS_JSON = "atlas.json"
ATLAS_MD = "ATLAS.md"
JOBS_DIR = "jobs"
RESULTS_DIR = "results"

SKIP_DIRS = {
    ".git", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "atlas-out", "graphify-out", "dist", "build", ".idea", ".vscode",
}
SKIP_FILES = {"ATLAS.md"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c",
             ".h", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift", ".kt", ".sh", ".ps1"}
DOC_EXTS = {".md", ".txt", ".rst", ".docx", ".pdf", ".html", ".htm", ".chm"}
SHEET_EXTS = {".xlsx", ".xlsm", ".csv"}
IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}

STOPWORDS = set("""
the and for with that this from into your you are was were will have has not but can all each
other than then when where which while these those their them they his her its our out about
between through during before after above below under over again once here there what who whom
how why also any both few more most some such only own same too very just because until both
и в во не на что я он она мы вы ты они как а то все она так его но да ты к у же вы за бы по
ее мне было вот от меня еще нет о из ему теперь когда даже ну вдруг ли если уже или ни быть
был него до вас нибудь опять уж вам ведь там потом себя ничего ей может они тут где есть
надо ней для тебя чем самая были вот от меня еще мои сказать её всё тоже своей над своих
""".split())

PART_NUM_RE = re.compile(r"\b[A-Z]{1,4}[-_]?\d{2,5}[A-Z0-9]*(?:[-_][A-Z0-9]{1,10})*\b")
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_-]{2,}")
PY_SYMBOL_RE = re.compile(r"^\s*(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)
JS_SYMBOL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)|"
    r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)", re.M)


# ---------------------------------------------------------------- extraction

def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _docx_outline(path: Path):
    """Outline from .docx using only stdlib (docx is a zip of XML)."""
    headings, n_par, n_tab, snippet = [], 0, 0, ""
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml")
        root = ET.fromstring(xml)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        for p in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
            n_par += 1
            style = p.find(".//w:pStyle", ns)
            text = "".join(t.text or "" for t in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
            if style is not None and "Heading" in (style.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") or ""):
                if text.strip():
                    headings.append(text.strip()[:120])
            elif not snippet and text.strip():
                snippet = text.strip()[:200]
        n_tab = sum(1 for _ in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tbl"))
    except Exception as e:  # corrupt zip/xml
        return {"error": f"docx parse: {e}"}
    return {"headings": headings[:30], "paragraphs": n_par, "tables": n_tab, "snippet": snippet}


def _xlsx_outline(path: Path):
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("xl/workbook.xml")
        root = ET.fromstring(xml)
        sheets = [s.get("name", "?") for s in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet")]
        return {"sheets": sheets}
    except Exception as e:
        return {"error": f"xlsx parse: {e}"}


def _pdf_outline(path: Path):
    try:
        from pypdf import PdfReader  # optional dependency
        r = PdfReader(str(path))
        return {"pages": len(r.pages), "title": (r.metadata.title or "")[:100] if r.metadata else ""}
    except ImportError:
        pass
    except Exception:
        return {"error": "pdf parse failed"}
    try:  # page count without pypdf
        data = path.read_bytes()
        pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
        return {"pages": pages}
    except Exception as e:
        return {"error": f"pdf: {e}"}


def _text_outline(path: Path, ext: str):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"error": f"read: {e}"}
    if ext in CODE_EXTS:
        symbols = PY_SYMBOL_RE.findall(text) if ext == ".py" else []
        if ext != ".py":
            symbols = [a or b for a, b in JS_SYMBOL_RE.findall(text)] or []
        return {"symbols": symbols[:40], "lines": text.count("\n") + 1}
    headings = [l.strip("# ").strip()[:120] for l in text.splitlines()
                if l.startswith("#")][:30]
    snippet = next((l.strip()[:200] for l in text.splitlines() if l.strip() and not l.startswith("#")), "")
    return {"headings": headings, "lines": text.count("\n") + 1, "snippet": snippet}


def extract_file(path: Path, rel: str):
    ext = path.suffix.lower()
    size = path.stat().st_size
    rec = {
        "path": rel, "ext": ext, "size": size,
        "sha1": sha1_file(path) if size <= MAX_FILE_SIZE else None,
        "mtime": int(path.stat().st_mtime),
    }
    if ext == ".docx":
        rec["outline"] = _docx_outline(path)
    elif ext in (".xlsx", ".xlsm"):
        rec["outline"] = _xlsx_outline(path)
    elif ext == ".pdf":
        rec["outline"] = _pdf_outline(path)
    elif ext in DOC_EXTS or ext in CODE_EXTS or ext in SHEET_EXTS:
        rec["outline"] = _text_outline(path, ext)
    elif ext == ".csv":
        try:
            rec["outline"] = {"lines": sum(1 for _ in open(path, "rb"))}
        except Exception:
            rec["outline"] = {}

    # keywords + part numbers, shared across doc/code text
    try:
        if ext == ".docx":
            text = " ".join(rec.get("outline", {}).get("headings", [])) + " " + rec.get("outline", {}).get("snippet", "")
        elif ext in DOC_EXTS or ext in CODE_EXTS or ext in SHEET_EXTS:
            text = path.read_text(encoding="utf-8", errors="replace")[:200_000]
        elif ext in (".xlsx", ".xlsm"):
            text = " ".join(rec.get("outline", {}).get("sheets", []))
        else:
            text = ""
    except Exception:
        text = ""
    if text:
        words = [w.lower() for w in WORD_RE.findall(text) if w.lower() not in STOPWORDS]
        rec["keywords"] = [w for w, _ in Counter(words).most_common(10)]
        rec["part_numbers"] = sorted(set(PART_NUM_RE.findall(text)))[:20]
    return rec


def visible_git_files(root: Path):
    """Список tracked и неигнорируемых untracked-файлов; None вне Git.

    Git сам применяет .gitignore, поэтому локальные проекты, секреты и тяжёлые
    выходные каталоги не попадают ни в обход, ни в публичный индекс Atlas.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others",
             "--exclude-standard", "-z"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    paths = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        rel = os.fsdecode(raw)
        parts = Path(rel).parts
        if any(part in SKIP_DIRS for part in parts[:-1]) or parts[-1] in SKIP_FILES:
            continue
        if (root / rel).is_file():
            paths.append(rel)
    return paths


def scan(root: Path):
    """Извлечь записи только из доступных для публикации файлов проекта."""
    visible = visible_git_files(root)
    candidates = []
    if visible is not None:
        candidates = [root / rel for rel in visible]
    else:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if name not in SKIP_FILES:
                    candidates.append(Path(dirpath) / name)
    files = []
    for p in candidates:
        rel = str(p.relative_to(root)).replace(os.sep, "/")
        if p.suffix.lower() in IMG_EXTS:
            files.append({"path": rel, "ext": p.suffix.lower(), "size": p.stat().st_size,
                          "sha1": None, "mtime": int(p.stat().st_mtime)})
        else:
            files.append(extract_file(p, rel))
    files.sort(key=lambda r: r["path"])
    return files


# ------------------------------------------------------------------- clusters

def build_clusters(files, min_shared=2, max_clusters=12):
    """LLM-free clustering: files sharing >= min_shared keywords form a cluster."""
    kw2files = defaultdict(set)
    for f in files:
        for kw in f.get("keywords", []):
            kw2files[kw].add(f["path"])
    clusters = []
    seen = set()
    ranked_kws = sorted(kw2files.items(), key=lambda kv: -len(kv[1]))
    for kw, paths in ranked_kws:
        if len(clusters) >= max_clusters:
            break
        paths = {p for p in paths if p not in seen}
        if len(paths) < 2:
            continue
        common = Counter()
        for p in paths:
            rec = next((r for r in files if r["path"] == p), None)
            if rec:
                for k in rec.get("keywords", []):
                    common[k] += 1
        shared = [k for k, c in common.most_common(4) if c >= min_shared]
        label = ", ".join(shared[:3]) if shared else kw
        clusters.append({"label": label, "files": sorted(paths)[:25], "count": len(paths)})
        seen |= paths
    return clusters


# ------------------------------------------------------------------ ATLAS.md

def render_atlas_md(root: Path, files, clusters, jobs_summary):
    total_size = sum(f["size"] for f in files)
    lines = [
        f"# ATLAS — {root.name or root}",
        "",
        f"Files: {len(files)} · Size: {total_size/1024/1024:.1f} MB · Generated by `atlas.py`",
        "",
        "> ORIENTATION RULES FOR THE AGENT:",
        "> 1. This file is the project memory. Read it first; do NOT re-scan the tree.",
        "> 2. Targeted reads only: use `atlas.py query \"<term>\"` to locate files/sections.",
        "> 3. After changing files run: `python3 scripts/atlas.py update`",
        "> 4. For batch work use a job manifest (see references/batch-processing.md).",
        "",
        "## Directory map",
        "",
    ]
    dirmap = defaultdict(lambda: [0, 0])
    for f in files:
        d = os.path.dirname(f["path"]) or "(root)"
        dirmap[d][0] += 1
        dirmap[d][1] += f["size"]
    for d in sorted(dirmap):
        n, s = dirmap[d]
        lines.append(f"- `{d}/` — {n} files, {s/1024:.0f} KB")

    if jobs_summary:
        lines += ["", "## Batch jobs", "",
                  "| job | done | pending | failed |",
                  "| --- | --- | --- | --- |"]
        for j in jobs_summary:
            lines.append(f"| {j['job']} | {j['done']} | {j['pending']} | {j['failed']} |")

    lines += ["", "## Key documents (top by size)", ""]
    for f in sorted(files, key=lambda r: -r["size"])[:15]:
        if f["ext"] in IMG_EXTS:
            continue
        title = ", ".join(f.get("outline", {}).get("headings", [])[:2]) or f.get("outline", {}).get("snippet", "")[:60]
        lines.append(f"- `{f['path']}` ({f['size']/1024:.0f} KB)" + (f" — {title}" if title else ""))

    part_idx = defaultdict(list)
    for f in files:
        for pn in f.get("part_numbers", []):
            part_idx[pn].append(f["path"])
    if part_idx:
        lines += ["", "## Part / model numbers", ""]
        for pn in sorted(part_idx)[:40]:
            lines.append(f"- `{pn}` — {len(part_idx[pn])} file(s): {', '.join('`'+p+'`' for p in part_idx[pn][:3])}")

    if clusters:
        lines += ["", "## Topic clusters", ""]
        for c in clusters:
            lines.append(f"- **{c['label']}** ({c['count']} files): {', '.join('`'+p+'`' for p in c['files'][:5])}")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ commands

def out_root(root: Path) -> Path:
    d = root / OUT_DIR
    (d / JOBS_DIR).mkdir(parents=True, exist_ok=True)
    (d / RESULTS_DIR).mkdir(parents=True, exist_ok=True)
    return d


def cmd_build(root: Path):
    files = scan(root)
    od = out_root(root)
    (od / ATLAS_JSON).write_text(json.dumps({"root": str(root), "files": files},
                                            ensure_ascii=False, indent=1), encoding="utf-8")
    clusters = build_clusters(files)
    jobs = jobs_summary(root)
    (root / ATLAS_MD).write_text(render_atlas_md(root, files, clusters, jobs), encoding="utf-8")
    print(f"ATLAS built: {len(files)} files -> {ATLAS_MD}, {OUT_DIR}/{ATLAS_JSON}")
    print("Run `python3 scripts/atlas.py query \"<term>\"` to locate content.")


def cmd_update(root: Path):
    od = out_root(root)
    old_path = od / ATLAS_JSON
    if not old_path.exists():
        print("No existing atlas — running full build.")
        return cmd_build(root)
    old = {f["path"]: f for f in json.loads(old_path.read_text(encoding="utf-8"))["files"]}
    new_files = scan(root)
    new_paths = {f["path"] for f in new_files}
    added = [f for f in new_files if f["path"] not in old]
    changed = [f for f in new_files if f["path"] in old and f.get("sha1") and f["sha1"] != old[f["path"]].get("sha1")]
    removed = [p for p in old if p not in new_paths]
    (od / ATLAS_JSON).write_text(json.dumps({"root": str(root), "files": new_files},
                                            ensure_ascii=False, indent=1), encoding="utf-8")
    clusters = build_clusters(new_files)
    (root / ATLAS_MD).write_text(render_atlas_md(root, new_files, clusters, jobs_summary(root)), encoding="utf-8")
    print(f"ATLAS updated: +{len(added)} new, ~{len(changed)} changed, -{len(removed)} removed "
          f"(only changed files were re-extracted)")
    # invalidate done-marked job entries whose file changed
    for jp in (od / JOBS_DIR).glob("*.json"):
        job = json.loads(jp.read_text(encoding="utf-8"))
        dirty = False
        for e in job["files"]:
            if e["status"] == "done" and e["sha1"] not in {f.get("sha1") for f in changed}:
                rec = next((f for f in new_files if f["path"] == e["path"]), None)
                if rec is None or rec.get("sha1") != e["sha1"]:
                    e["status"] = "pending"
                    dirty = True
        if dirty:
            jp.write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"job '{jp.stem}': changed files re-queued")


def cmd_query(root: Path, text: str):
    od = root / OUT_DIR
    data = json.loads((od / ATLAS_JSON).read_text(encoding="utf-8"))
    terms = [t.lower() for t in re.split(r"\s+", text) if t]
    hits = []
    for f in data["files"]:
        hay = (f["path"] + " " + " ".join(f.get("keywords", [])) + " " +
               " ".join(f.get("part_numbers", [])) + " " +
               " ".join(f.get("outline", {}).get("headings", []))).lower()
        score = sum(hay.count(t) for t in terms)
        if score:
            hits.append((score, f))
    hits.sort(key=lambda x: -x[0])
    if not hits:
        print(f"No matches for '{text}'.")
        return
    for score, f in hits[:20]:
        hs = "; ".join(f.get("outline", {}).get("headings", [])[:2])
        print(f"[{score}] {f['path']} ({f['ext']}, {f['size']/1024:.0f} KB)" + (f" — {hs}" if hs else ""))


def cmd_related(root: Path, target: str):
    data = json.loads((root / OUT_DIR / ATLAS_JSON).read_text(encoding="utf-8"))
    rec = next((f for f in data["files"] if f["path"] == target or f["path"].endswith(target)), None)
    if not rec:
        print(f"File '{target}' not in atlas.")
        return
    kws = set(rec.get("keywords", []))
    scored = []
    for f in data["files"]:
        if f["path"] == rec["path"]:
            continue
        shared = kws & set(f.get("keywords", []))
        if shared:
            scored.append((len(shared), sorted(shared), f["path"]))
    scored.sort(key=lambda x: -x[0])
    print(f"Files related to {rec['path']} (shared keywords):")
    for n, shared, p in scored[:15]:
        print(f"  [{n}] {p}  ({', '.join(shared[:4])})")


def _job_path(root: Path, job: str) -> Path:
    if not re.fullmatch(r"[\w.-]+", job):
        raise SystemExit(f"Invalid job name: {job!r}")
    return root / OUT_DIR / JOBS_DIR / f"{job}.json"


def cmd_manifest(root: Path, job: str, targets):
    paths = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            paths += sorted(x for x in p.rglob("*") if x.is_file() and x.suffix.lower() not in IMG_EXTS)
        else:
            paths.append(p)
    entries = []
    for p in paths:
        rel = str(p.relative_to(root)) if p.is_absolute() else str(p)
        if p.exists():
            entries.append({"path": rel.replace(os.sep, "/"), "sha1": sha1_file(p), "status": "pending",
                            "result": "", "error": ""})
    jp = _job_path(root, job)
    if jp.exists():
        old = {e["path"]: e for e in json.loads(jp.read_text(encoding="utf-8"))["files"]}
        for e in entries:
            prev = old.get(e["path"])
            if prev and prev["sha1"] == e["sha1"] and prev["status"] in ("done", "failed"):
                e["status"] = prev["status"]
                e["result"] = prev.get("result", "")
                e["error"] = prev.get("error", "")
    jp.write_text(json.dumps({"job": job, "files": entries}, ensure_ascii=False, indent=1), encoding="utf-8")
    done = sum(1 for e in entries if e["status"] == "done")
    print(f"Job '{job}': {len(entries)} files ({done} already done, {len(entries)-done} pending)")
    print(f"Results dir: {OUT_DIR}/{RESULTS_DIR}/{job}/")


def _set_status(root: Path, job: str, file: str, status: str, note: str = ""):
    jp = _job_path(root, job)
    data = json.loads(jp.read_text(encoding="utf-8"))
    e = next((x for x in data["files"] if x["path"] == file or x["path"].endswith(file)), None)
    if not e:
        raise SystemExit(f"{file} not in job '{job}'.")
    e["status"] = status
    if status == "done":
        e["result"] = note or f"{OUT_DIR}/{RESULTS_DIR}/{job}/{Path(file).stem}/"
    else:
        e["error"] = note
    jp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_status(root: Path, job: str):
    data = json.loads(_job_path(root, job).read_text(encoding="utf-8"))
    files = data["files"]
    done = [e for e in files if e["status"] == "done"]
    failed = [e for e in files if e["status"] == "failed"]
    pending = [e for e in files if e["status"] == "pending"]
    print(f"Job '{job}': {len(done)}/{len(files)} done, {len(pending)} pending, {len(failed)} failed")
    for e in failed[:10]:
        print(f"  FAILED: {e['path']} — {e['error'][:100]}")
    for e in pending[:10]:
        print(f"  pending: {e['path']}")
    if len(pending) > 10:
        print(f"  ... and {len(pending)-10} more pending")


def jobs_summary(root: Path):
    out = []
    jd = root / OUT_DIR / JOBS_DIR
    if not jd.exists():
        return out
    for jp in sorted(jd.glob("*.json")):
        data = json.loads(jp.read_text(encoding="utf-8"))
        files = data["files"]
        out.append({
            "job": data["job"],
            "done": sum(1 for e in files if e["status"] == "done"),
            "pending": sum(1 for e in files if e["status"] == "pending"),
            "failed": sum(1 for e in files if e["status"] == "failed"),
        })
    return out


# ---------------------------------------------------------------------- main

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd, rest = args[0], args[1:]
    if cmd in ("build", "update"):
        cmd_build_or_update = cmd_build if cmd == "build" else cmd_update
        cmd_build_or_update(Path(rest[0]).resolve() if rest else Path(".").resolve())
        return
    if cmd == "query" and len(rest) > 1 and Path(rest[-1]).is_dir():
        root, text = Path(rest[-1]).resolve(), " ".join(rest[:-1])
    else:
        root, text = Path(".").resolve(), " ".join(rest)
    if cmd == "query":
        cmd_query(root, text)
    elif cmd == "related":
        cmd_related(root, rest[0])
    elif cmd == "manifest":
        cmd_manifest(root, rest[0], rest[1:])
    elif cmd == "status":
        cmd_status(root, rest[0])
    elif cmd == "done":
        _set_status(root, rest[0], rest[1], "done", rest[2] if len(rest) > 2 else "")
        print(f"OK: {rest[1]} marked done.")
    elif cmd == "fail":
        _set_status(root, rest[0], rest[1], "failed", rest[2] if len(rest) > 2 else "")
        print(f"OK: {rest[1]} marked failed.")
    else:
        raise SystemExit(f"Unknown command: {cmd}\n{__doc__}")


if __name__ == "__main__":
    main()
