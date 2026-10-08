#!/usr/bin/env python3
"""webapp.py — веб-интерфейс мастера генерации маршрутов (ТЗ, v2).

Один процесс FastAPI: мастер (создание проекта → входные → анализ → погода →
документы → результат) и вкладка «Обучение» (правила генерации и база примеров,
которые LLM-агент подмешивает в промпты F4).

Запуск:
  pip install -r requirements-web.txt
  python3 webapp.py            # http://127.0.0.1:8077
  python3 webapp.py --host 0.0.0.0 --port 8077   # доступ из сети/сервера

Проекты лежат в projects/<маршрут>/: «входные/» (track.gpx, points.json,
события.json, чеклист.json) и «выходные/» (всё, что производят скрипты).
После каждого удачного шага автоматически обновляется СТАТУС (F9, контракт).
"""
import argparse, io, importlib.util, json, os, subprocess, sys, zipfile
from pathlib import Path
from urllib.parse import quote

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
import uvicorn

BASE = Path(__file__).resolve().parent
SCRIPTS = BASE / "scripts"
PROJECTS = BASE / "projects"
LEARN = BASE / "learn"
RULES_FILE = LEARN / "правила.md"
EXAMPLES_FILE = LEARN / "примеры.json"

# канонические имена входных файлов проекта (мастер сохраняет загрузки под ними)
IN_DIR, OUT_DIR = "входные", "выходные"

app = FastAPI(title="Генератор путеводителей горных походов")


def safe_name(name):
    """Имя проекта/файла: без слэшей и служебных символов, кириллица разрешена."""
    name = (name or "").strip().strip(".")
    if not name or any(c in name for c in '/\\:*?"<>|') or ".." in name:
        raise HTTPException(400, f"Недопустимое имя: {name!r}")
    return name


def project_dir(name):
    d = PROJECTS / safe_name(name)
    if not d.is_dir():
        raise HTTPException(404, f"Проект «{name}» не найден")
    return d


def run_script(args, cwd=BASE, timeout=600, stdin_text=None, env_extra=None):
    """Запуск скрипта из scripts/ с UTF-8-окружением; возвращает (ok, stdout, stderr)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", **(env_extra or {}))
    r = subprocess.run([sys.executable, *map(str, args)], cwd=cwd, env=env,
                       input=stdin_text, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode == 0, r.stdout, r.stderr


def update_status(proj):
    """F9-контракт: СТАТУС обновляется после каждого изменения выдачи."""
    ok, _, err = run_script([SCRIPTS / "make_status.py", proj])
    return ok, err


def load_script_module(name):
    """Импорт модуля из scripts/ по имени без .py (скрипты — не пакет, поэтому так)."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def track_bbox(gpx_path, margin=0.05):
    """Bbox трека (S, N, W, E) с полем margin градусов — для валидации KML."""
    ga = load_script_module("gpx_analyze")
    trkpts, _ = ga.load_gpx(str(gpx_path))
    lats = [p[0] for p in trkpts]
    lons = [p[1] for p in trkpts]
    return [min(lats) - margin, max(lats) + margin,
            min(lons) - margin, max(lons) + margin]


# ---------- мастер: проекты ----------

@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE / "wizard.html").read_text(encoding="utf-8")


@app.get("/api/projects")
def list_projects():
    PROJECTS.mkdir(exist_ok=True)
    out = []
    for d in sorted(PROJECTS.iterdir()):
        if d.is_dir():
            out.append({"name": d.name,
                        "files_in": len(list((d / IN_DIR).glob("*"))) if (d / IN_DIR).is_dir() else 0,
                        "files_out": len(list((d / OUT_DIR).glob("*"))) if (d / OUT_DIR).is_dir() else 0})
    return out


@app.post("/api/projects")
def create_project(payload: dict = Body(...)):
    name = safe_name(payload.get("name"))
    d = PROJECTS / name
    d.mkdir(parents=True, exist_ok=True)
    (d / IN_DIR).mkdir(exist_ok=True)
    (d / OUT_DIR).mkdir(exist_ok=True)
    update_status(d)
    return {"ok": True, "name": name}


@app.post("/api/projects/{name}/upload")
def upload(name, payload: dict = Body(...)):
    """Сохранить входной файл: {"filename", "text"} для текста или
    {"filename", "content_b64"} для бинарных (PDF/DOCX)."""
    d = project_dir(name)
    fname = safe_name(payload.get("filename"))
    (d / IN_DIR).mkdir(exist_ok=True)
    if payload.get("content_b64") is not None:
        import base64
        (d / IN_DIR / fname).write_bytes(base64.b64decode(payload["content_b64"]))
        size = (d / IN_DIR / fname).stat().st_size
    elif payload.get("text") is not None:
        (d / IN_DIR / fname).write_text(payload["text"], encoding="utf-8")
        size = len(payload["text"])
    else:
        raise HTTPException(400, "Нужно поле text или content_b64")
    return {"ok": True, "filename": fname, "size": size}


@app.get("/api/projects/{name}/files")
def files(name):
    d = project_dir(name)
    def ls(sub):
        p = d / sub
        return sorted(f.name for f in p.glob("*") if f.is_file()) if p.is_dir() else []
    return {"входные": ls(IN_DIR), "выходные": ls(OUT_DIR),
            "статус": sorted(f.name for f in d.glob("СТАТУС_*.md"))}


@app.get("/api/projects/{name}/read")
def read_file(name, path):
    d = project_dir(name)
    p = (d / path).resolve()
    if not str(p).startswith(str(d.resolve())) or not p.is_file():
        raise HTTPException(404, "Файл не найден")
    return {"text": p.read_text(encoding="utf-8", errors="replace")}


# ---------- мастер: шаги генерации ----------

def step_program(d, params):
    """F1: прочитать программу (PDF/DOCX/TXT), извлечь текст и черновик точек."""
    src = params.get("filename")
    if src:
        src = d / IN_DIR / safe_name(src)
    else:  # по умолчанию — первый подходящий файл во входных
        for ext in ("pdf", "docx", "txt", "md"):
            found = sorted((d / IN_DIR).glob(f"*.{ext}"))
            if found:
                src = found[0]
                break
    if not src or not src.is_file():
        raise HTTPException(400, "Загрузите программу (PDF/DOCX/TXT) или вставьте текст")
    args = [SCRIPTS / "read_program.py", src,
            "--out-points", d / IN_DIR / "points_draft.json"]
    if src.name != "программа.txt":  # не затирать ручной текст производным файлом
        args += ["--out-text", d / IN_DIR / "программа.txt"]
    return (*run_script(args),)


def step_analyze(d, params):
    gpx = d / IN_DIR / "track.gpx"
    if not gpx.is_file():
        raise HTTPException(400, "Загрузите входные/track.gpx")
    args = [SCRIPTS / "gpx_analyze.py", gpx]
    if (d / IN_DIR / "points.json").is_file():
        args += ["--points", d / IN_DIR / "points.json"]
    ok, out, err = run_script(args)
    if ok:
        (d / OUT_DIR).mkdir(exist_ok=True)
        (d / OUT_DIR / "анализ.json").write_text(out, encoding="utf-8")
    return ok, out, err


def step_weather(d, params):
    pts = d / IN_DIR / "points.json"
    if not pts.is_file():
        raise HTTPException(400, "Загрузите входные/points.json (с полем ele у точек)")
    start, end = params.get("start"), params.get("end")
    if not start or not end:
        raise HTTPException(400, "Укажите даты start и end")
    args = [SCRIPTS / "weather.py", pts, "--start", start, "--end", end,
            "--out", d / OUT_DIR / "погода.json", "--md", d / OUT_DIR / "Погода.md"]
    return (*run_script(args, timeout=900),)


def step_kml(d, params):
    gpx = d / IN_DIR / "track.gpx"
    if not gpx.is_file():
        raise HTTPException(400, "Загрузите входные/track.gpx")
    bbox = track_bbox(gpx)
    args = [SCRIPTS / "make_kml.py", gpx, d / OUT_DIR / "маршрут.kml",
            "--bbox", *[f"{x:.4f}" for x in bbox]]
    splits = params.get("split_km") or []
    if splits:
        args += ["--split-km", *[str(x) for x in splits]]
    marks_src = d / IN_DIR / "points.json"
    if marks_src.is_file():
        pts = json.loads(marks_src.read_text(encoding="utf-8"))
        marks = [{"name": p["name"], "lat": p["lat"], "lon": p["lon"],
                  "desc": f"{p.get('ele', '?')} м"} for p in pts]
        mf = d / IN_DIR / "marks.json"
        mf.write_text(json.dumps(marks, ensure_ascii=False, indent=1), encoding="utf-8")
        args += ["--marks", mf]
    return (*run_script(args),)


def step_ics(d, params):
    ev = d / IN_DIR / "события.json"
    if not ev.is_file():
        raise HTTPException(400, "Сохраните входные/события.json (редактор на шаге «Документы»)")
    return (*run_script([SCRIPTS / "make_ics.py", ev, d / OUT_DIR / "календарь.ics"]),)


def step_checklist(d, params):
    src = d / IN_DIR / "чеклист.json"
    if not src.is_file():
        raise HTTPException(400, "Сохраните входные/чеклист.json (редактор на шаге «Документы»)")
    return (*run_script([SCRIPTS / "make_checklist.py", src, d / OUT_DIR / "Чеклист.html"]),)


def step_status(d, params):
    return (*run_script([SCRIPTS / "make_status.py", d]),)


def watch_and_planned(d):
    """Треки проекта: записанный с часов (приоритет для времени) и плановый."""
    watch = d / IN_DIR / "трек_с_часов.gpx"
    planned = d / IN_DIR / "track.gpx"
    return (watch if watch.is_file() else None,
            planned if planned.is_file() else None)


def step_photos(d, params):
    """Сортировка фото по точкам/дням маршрута (EXIF GPS или время на треке)."""
    folder = (params.get("folder") or "").strip()
    if not folder:
        raise HTTPException(400, "Укажите путь к папке с фотографиями")
    pts = d / IN_DIR / "points.json"
    if not pts.is_file():
        raise HTTPException(400, "Нужен входные/points.json (шаг «Программа»)")
    args = [SCRIPTS / "photo_sort.py", folder, "--points", pts, "--out", d / OUT_DIR]
    watch, planned = watch_and_planned(d)
    gpx = watch or planned  # привязка по времени — в первую очередь по записанному треку
    if gpx:
        args += ["--gpx", gpx]
    if params.get("start"):
        args += ["--start", params["start"]]
    return (*run_script(args, timeout=1800),)


def step_marks(d, params):
    """Фотометки: привязка фото/видео к точкам аудиогида 🎧 (GPX проекта)."""
    folder = (params.get("folder") or "").strip()
    if not folder:
        raise HTTPException(400, "Укажите путь к папке с фотографиями")
    watch, planned = watch_and_planned(d)
    if not planned:
        raise HTTPException(400, "Нужен входные/track.gpx с точками 🎧 аудиогида")
    args = [SCRIPTS / "photo_marks.py", folder, "--gpx", planned, "--out", d / OUT_DIR]
    if watch:
        args += ["--track-gpx", watch]  # время — по записанному треку с часов
    if (d / IN_DIR / "points.json").is_file():
        args += ["--points", d / IN_DIR / "points.json"]
    return (*run_script(args, timeout=1800),)


def step_photos_all(d, params):
    """Всё про фото одной кнопкой: сортировка → фотометки → гео-отчёт с картой.
    Каждый подшаг терпим к отсутствию входных: пропуск с пояснением, не падение."""
    folder = (params.get("folder") or "").strip()
    if not folder:
        raise HTTPException(400, "Сначала выберите папку с фотографиями")
    logs, any_ok = [], False

    sub = [("Сортировка по точкам и дням", step_photos),
           ("Фотометки к аудиогиду", step_marks)]
    for title, fn in sub:
        try:
            ok, out, err = fn(d, params)
        except HTTPException as e:
            ok, out, err = False, "", f"пропущено: {e.detail}"
        any_ok |= ok
        tail = (err or out).strip().splitlines()
        logs.append(f"— {title}: {'готово' if ok else 'не выполнено'}\n  " +
                    "\n  ".join(tail[-4:]))

    # гео-фото-отчёт с картой (hike_report.py) — только если стоят зависимости
    try:
        import folium, openpyxl, reverse_geocoder  # noqa: F401
        have_deps = True
    except ImportError:
        have_deps = False
    if have_deps:
        ok, out, err = run_hike_report(d, folder, params)
        any_ok |= ok
        tail = (out or err).strip().splitlines()
        logs.append("— Отчёт с картой (hike_report): " +
                    ("готово — файлы в папке с фото" if ok else "ошибка") +
                    "\n  " + "\n  ".join(tail[-8:]))
    else:
        logs.append("— Отчёт с картой (hike_report): пропущено — нет зависимостей "
                    "(pip install folium openpyxl reverse-geocoder pyosmogps)")
    return any_ok, "", "\n".join(logs)


def run_hike_report(d, folder, params):
    """Запуск hike_report.py с настройками модуля «Фотоотчёт»:
    пояс похода, макс. разрыв привязки, офлайн-тайлы, оценка по плану."""
    args = [SCRIPTS / "hike_report.py", folder]
    watch, planned = watch_and_planned(d)
    extra = [t for t in (watch, planned) if t]  # записанный + плановый треки
    if extra:
        args += ["--gpx", *extra]
    if params.get("tz_offset") not in (None, ""):
        args += ["--tz-offset", str(params["tz_offset"])]
    if params.get("max_gap_min") not in (None, ""):
        args += ["--max-gap-min", str(params["max_gap_min"])]
    if params.get("plan_interp") is False:
        args += ["--no-plan"]
    # офлайн-тайлы качаются минуты — по умолчанию выключены, включаются галочкой
    env = {} if params.get("offline_tiles") else {"HIKE_OFFLINE_MAP": "0"}
    timeout = 3600 if params.get("offline_tiles") else 1200
    return run_script(args, timeout=timeout, stdin_text="\n\n", env_extra=env)


def step_report_map(d, params):
    """Только гео-фото-отчёт с картой (hike_report) с настройками модуля."""
    folder = (params.get("folder") or "").strip()
    if not folder:
        raise HTTPException(400, "Сначала выберите папку с фотографиями")
    try:
        import folium, openpyxl, reverse_geocoder  # noqa: F401
    except ImportError:
        raise HTTPException(400, "Нужны зависимости: pip install folium openpyxl "
                                 "reverse-geocoder pyosmogps")
    ok, out, err = run_hike_report(d, folder, params)
    tail = (out or err).strip().splitlines()
    return ok, "", "\n".join(tail[-10:])


def step_guide(d, params):
    """F4: генерация MD-гида через OpenRouter (модель из настроек шага)."""
    llm = _llm_mod()
    model = (params.get("model") or "").strip() or None
    key = (params.get("api_key") or "").strip() or None
    try:
        out = llm.generate_guide(d, model=model, key=key)
        return True, "", f"✓ Гид записан: {out.name} (модель: {model or llm.load_config().get('model') or 'по умолчанию'})"
    except SystemExit as e:
        return False, "", str(e)


def step_research(d, params):
    """Сбор фактов по маршруту (Википедия + OSM) → Факты.md для LLM-гида."""
    pts = d / IN_DIR / "points.json"
    if not pts.is_file():
        raise HTTPException(400, "Нужен входные/points.json (шаг «Программа»)")
    args = [SCRIPTS / "research.py", pts, "--out", d / OUT_DIR, "--region", d.name]
    if (d / IN_DIR / "track.gpx").is_file():
        args += ["--gpx", d / IN_DIR / "track.gpx"]
    return (*run_script(args, timeout=600),)


def step_guide_html(d, params):
    """HTML-версия Гид.md (офлайн, профиль высот, печать)."""
    return (*run_script([SCRIPTS / "make_guide_html.py", d]),)


def step_audio_texts(d, params):
    """Тексты аудиогида через LLM (числа прописью) → аудиотексты.json."""
    llm = _llm_mod()
    model = (params.get("model") or "").strip() or None
    key = (params.get("api_key") or "").strip() or None
    try:
        out = llm.generate_audio_texts(d, model=model, key=key)
        return True, "", f"✓ Тексты аудиогида: {out.name}"
    except SystemExit as e:
        return False, "", str(e)


def step_tts(d, params):
    """Озвучка аудиотекстов (edge-tts) → выходные/Аудиогид/*.mp3 + zip."""
    texts = d / OUT_DIR / "аудиотексты.json"
    if not texts.is_file():
        raise HTTPException(400, "Сначала сгенерируйте тексты аудиогида (кнопка выше)")
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        raise HTTPException(400, "Нужен edge-tts: pip install edge-tts -i https://pypi.org/simple")
    ok, out, err = run_script([SCRIPTS / "tts_audioguide.py", texts, d / OUT_DIR / "Аудиогид"],
                              timeout=3600)
    if ok:  # упаковать в zip (контракт выдачи аудиогида)
        zpath = d / OUT_DIR / "Аудиогид.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted((d / OUT_DIR / "Аудиогид").glob("*.mp3")):
                z.write(f, f"Аудиогид/{f.name}")
        err += f"\n✓ {zpath.name}: {len(list((d / OUT_DIR / 'Аудиогид').glob('*.mp3')))} треков"
    return ok, out, err


def step_daylight(d, params):
    """Световой день и ночное небо: рассвет/закат (NOAA), фаза Луны."""
    pts = d / IN_DIR / "points.json"
    if not pts.is_file():
        raise HTTPException(400, "Нужен входные/points.json (шаг «Программа»)")
    start, end = params.get("start"), params.get("end")
    if not start or not end:
        raise HTTPException(400, "Укажите даты проекта (шаг 1)")
    return (*run_script([SCRIPTS / "daylight.py", pts, "--start", start, "--end", end,
                         "--md", d / OUT_DIR / "Световой_день.md"]),)


def step_first_aid(d, params):
    """Аптечка: чеклист (HTML + Keep) и ICS-напоминания о приёме."""
    pts = d / IN_DIR / "points.json"
    if not pts.is_file():
        raise HTTPException(400, "Нужен входные/points.json (шаг «Программа»)")
    start, end = params.get("start"), params.get("end")
    if not start or not end:
        raise HTTPException(400, "Укажите даты проекта (шаг 1)")
    out = d / OUT_DIR
    ok1, _, err1 = run_script([SCRIPTS / "first_aid.py", pts, "--start", start,
                               "--end", end, "--out", out])
    if not ok1:
        return False, "", err1
    ok2, _, err2 = run_script([SCRIPTS / "make_checklist.py", out / "аптечка_чеклист.json",
                               out / "Аптечка.html", "--keep", out / "Аптечка_Keep.txt"])
    ok3, _, err3 = run_script([SCRIPTS / "make_ics.py", out / "аптечка_напоминания.json",
                               out / "аптечка_напоминания.ics"])
    return ok1 and ok2 and ok3, "", "\n".join(x.strip() for x in (err1, err2, err3) if x)


def step_currency(d, params):
    """Курсы валют стран маршрута (F10) → Деньги.md."""
    codes = (params.get("currencies") or "BYN,UZS,TJS").strip()
    return (*run_script([SCRIPTS / "currency.py", "--currencies", codes,
                         "--md", d / OUT_DIR / "Деньги.md"]),)


def step_report(d, params):
    """Отчёт о пройденном походе: записанный трек + описание + дописки."""
    return (*run_script([SCRIPTS / "make_report.py", d]),)


STEPS = {"program": step_program, "analyze": step_analyze, "weather": step_weather,
         "guide": step_guide, "guide_html": step_guide_html, "research": step_research,
         "audio_texts": step_audio_texts, "tts": step_tts,
         "daylight": step_daylight, "first_aid": step_first_aid, "currency": step_currency,
         "report": step_report,
         "kml": step_kml, "ics": step_ics, "checklist": step_checklist,
         "photos": step_photos, "marks": step_marks, "photos_all": step_photos_all,
         "report_map": step_report_map, "status": step_status}


@app.post("/api/projects/{name}/run/{step}")
def run_step(name, step, payload: dict = Body(default={})):
    if step not in STEPS:
        raise HTTPException(404, f"Неизвестный шаг: {step}")
    d = project_dir(name)
    try:
        ok, out, err = STEPS[step](d, payload)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Шаг превысил таймаут")
    status_ok, status_err = (True, "") if step == "status" else update_status(d)
    return {"ok": ok, "stdout": out, "stderr": err,
            "status_ok": status_ok, "status_stderr": status_err}


@app.post("/api/projects/{name}/note")
def add_note(name, payload: dict = Body(...)):
    """Дописка к отчёту: свободный текст И/ИЛИ файл-вложение (PDF/DOCX/TXT —
    текст извлекается read_program.py). Абзац «день N: …» попадёт в день N."""
    d = project_dir(name)
    parts = []
    text = (payload.get("text") or "").strip()
    if text:
        parts.append(text)
    fname = (payload.get("filename") or "").strip()
    if fname:
        src = d / IN_DIR / safe_name(fname)
        if not src.is_file():
            raise HTTPException(404, f"Файл «{fname}» не найден во входных")
        if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".heic"):
            raise HTTPException(400, "Текст из изображений не распознаётся (нет OCR) — "
                                     "опишите фото текстом")
        rp = load_script_module("read_program")
        try:
            extracted = rp.extract_text(str(src)).strip()
        except SystemExit as e:
            raise HTTPException(400, str(e))
        if extracted:
            parts.append(extracted)
    if not parts:
        raise HTTPException(400, "Пустая дописка")
    p = d / IN_DIR / "дописки.txt"
    p.parent.mkdir(exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        for part in parts:
            f.write("\n\n" + part + "\n")
    return {"ok": True, "added_chars": sum(len(x) for x in parts)}


# ---------- мастер: результат ----------

MEDIA_EXT = {".jpg", ".jpeg", ".mp4", ".mov", ".heic"}


@app.get("/api/browse")
def browse(path: str = ""):
    """Проводник по папкам компьютера для выбора директории с фото."""
    if not path:
        roots, seen = [], set()

        def add(name, p):
            p = Path(p)
            key = str(p).lower()
            if p.is_dir() and key not in seen:
                seen.add(key)
                roots.append({"name": name, "path": str(p), "media": None})

        if os.name == "nt":
            for c in "CDEFGH":
                add(f"Диск {c}:\\", f"{c}:/")
        home = Path.home()
        od = Path(os.environ.get("OneDrive", home))
        add("Документы", home / "Documents")
        add("Документы (OneDrive)", od / "Documents")
        add("Документы (OneDrive, ru)", od / "Документы")
        add("Рабочий стол", home / "Desktop")
        add("Загрузки", home / "Downloads")
        add("Изображения", home / "Pictures")
        add("Изображения (OneDrive)", od / "Pictures")
        add("Домашняя папка", home)
        return {"path": "", "parent": None, "dirs": roots}

    p = Path(path)
    if not p.is_dir():
        raise HTTPException(404, "Папка не найдена")
    dirs = []
    try:
        subs = sorted(p.iterdir())
    except PermissionError:
        raise HTTPException(403, "Нет доступа к папке")
    for sub in subs:
        if not sub.is_dir() or sub.name.startswith((".", "$")):
            continue
        try:
            media = sum(1 for f in sub.iterdir() if f.suffix.lower() in MEDIA_EXT)
        except (PermissionError, OSError):
            media = None
        dirs.append({"name": sub.name, "path": str(sub), "media": media})
    try:
        media_here = sum(1 for f in p.iterdir()
                         if f.is_file() and f.suffix.lower() in MEDIA_EXT)
    except (PermissionError, OSError):
        media_here = None
    parent = "" if p.parent == p else str(p.parent)
    return {"path": str(p), "parent": parent, "dirs": dirs, "media_here": media_here}

@app.get("/api/projects/{name}/download")
def download(name, path):
    d = project_dir(name)
    p = (d / path).resolve()
    if not str(p).startswith(str(d.resolve())) or not p.is_file():
        raise HTTPException(404, "Файл не найден")
    return FileResponse(p, filename=p.name)


@app.get("/api/projects/{name}/zip")
def zip_project(name):
    d = project_dir(name)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(d.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(d.parent))
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition":
                             f"attachment; filename*=UTF-8''{quote(d.name)}.zip"})


# ---------- LLM (OpenRouter) ----------

def _llm_mod():
    """Модуль llm.py (OpenRouter) — ленивый импорт, чтобы без ключа мастер работал."""
    return load_script_module("llm")


@app.get("/api/llm")
def llm_get():
    llm = _llm_mod()
    cfg = llm.load_config()
    key = cfg.get("api_key") or os.environ.get("OPENROUTER_API_KEY", "")
    return {"model": cfg.get("model") or "",
            "has_key": bool(key),
            "key_masked": (key[:7] + "…" + key[-4:]) if key else "",
            "default_free": None}


@app.put("/api/llm")
def llm_put(payload: dict = Body(...)):
    llm = _llm_mod()
    cfg = llm.load_config()
    if "api_key" in payload:
        cfg["api_key"] = payload["api_key"].strip()
    if "model" in payload:
        cfg["model"] = payload["model"].strip()
    llm.save_config(cfg)
    return {"ok": True, "model": cfg.get("model") or "", "has_key": bool(cfg.get("api_key"))}


@app.get("/api/llm/models")
def llm_models():
    """Живой список бесплатных моделей + рекомендуемая по умолчанию."""
    llm = _llm_mod()
    try:
        free = llm.list_free_models()
    except Exception as e:
        raise HTTPException(502, f"OpenRouter недоступен: {e}")
    return {"free": free, "default": llm.default_model()}


# ---------- обучение ----------

DEFAULT_RULES = """# Правила генерации (обучение)

Эти правила LLM-агент подмешивает в промпты при генерации гида (F4) и текстов
аудиогида. Пишите сюда короткие проверяемые правила, например:
- Все числа в текстах аудиогида — прописью.
- Уклоны называть только по таблице «тропа/уклон/сложность» из анализа.
- Сомнительные факты помечать «по отзывам».
"""


def read_examples():
    if EXAMPLES_FILE.is_file():
        return json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    return []


@app.get("/api/learn")
def learn_get():
    rules = RULES_FILE.read_text(encoding="utf-8") if RULES_FILE.is_file() else DEFAULT_RULES
    return {"rules": rules, "examples": read_examples()}


@app.put("/api/learn/rules")
def learn_rules(payload: dict = Body(...)):
    LEARN.mkdir(exist_ok=True)
    RULES_FILE.write_text(payload.get("text", ""), encoding="utf-8")
    return {"ok": True}


@app.post("/api/learn/examples")
def learn_example_add(payload: dict = Body(...)):
    """Пример = эталонная пара «вход → фрагмент выдачи» (few-shot для F4)."""
    LEARN.mkdir(exist_ok=True)
    ex = read_examples()
    ex.append({"title": payload.get("title", "").strip(),
               "input": payload.get("input", ""),
               "output": payload.get("output", ""),
               "tags": payload.get("tags", "")})
    EXAMPLES_FILE.write_text(json.dumps(ex, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "count": len(ex)}


@app.delete("/api/learn/examples/{idx}")
def learn_example_del(idx: int):
    ex = read_examples()
    if not 0 <= idx < len(ex):
        raise HTTPException(404, "Нет такого примера")
    ex.pop(idx)
    EXAMPLES_FILE.write_text(json.dumps(ex, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "count": len(ex)}


def lan_ip():
    """Локальный IP для доступа с телефона (та же Wi-Fi сеть)."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # пакет не отправляется — лишь выбор интерфейса
            return s.getsockname()[0]
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1",
                    help="0.0.0.0 — доступ с телефона/из сети")
    ap.add_argument("--port", type=int, default=8077)
    args = ap.parse_args()
    print(f"Мастер на этом компьютере: http://127.0.0.1:{args.port}")
    if args.host == "0.0.0.0":
        ip = lan_ip()
        if ip:
            print(f"С телефона (та же Wi-Fi):     http://{ip}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
