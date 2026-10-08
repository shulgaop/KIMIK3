#!/usr/bin/env python3
"""test_regression.py — регрессия на эталоне «Фанские горы» (без pytest).

Контрольные числа эталона (СТАТУС_Фанские_горы.md, проверено 27.09.2026):
87,45 км полного кольца · 2072 точки · высоты 1533–4739 м ·
уклоны ±40,6° окном 400 м · bbox 38.9–39.6N / 67.9–68.5E · новолуние 11–12.09.2026.

Запуск:  python3 scripts/test_regression.py
Выход: 0 — всё зелёное; 1 — есть падения (подробности в stderr).
"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
EX = BASE.parent / "examples" / "Фанские_горы"
GPX = EX / "Фанские_горы_Чимтарга_трек.gpx"

passed, failed = [], []


def check(name, cond, detail=""):
    (passed if cond else failed).append(name)
    print(("✓ " if cond else "✗ ") + name + (f"  ({detail})" if detail else ""))


def run(script, *args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")  # дочерние скрипты — UTF-8 (Windows cp1251)
    r = subprocess.run([sys.executable, BASE / script, *map(str, args)], env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout, r.stderr


def main():
    if hasattr(sys.stdout, "reconfigure"):  # Windows-консоль cp1251: не падать на ✓/✗
        sys.stdout.reconfigure(errors="replace")
    tmp = Path(tempfile.mkdtemp(prefix="routegen_test_"))

    # 1. gpx_analyze — контрольные числа эталона
    code, out, _ = run("gpx_analyze.py", GPX, "--window", 400)
    j = json.loads(out)
    check("gpx_analyze: километраж 87,45 км", abs(j["total_km"] - 87.45) < 0.05, f"{j['total_km']}")
    check("gpx_analyze: высоты 1533–4739", j["ele_min_m"] == 1533 and j["ele_max_m"] == 4739)
    check("gpx_analyze: 2072 точки", j["track_points"] == 2072)
    check("gpx_analyze: уклоны ±40,6° окном 400 м",
          abs(j["gradients"]["max_up_deg"] - 40.6) < 0.1
          and abs(j["gradients"]["max_down_deg"] + 40.6) < 0.1)

    # 2. make_kml — генерация + встроенная валидация
    code, _, err = run("make_kml.py", GPX, tmp / "тест.kml", "--bbox", 38.9, 39.6, 67.9, 68.5)
    check("make_kml: валидация пройдена", code == 0 and "валиден" in err)

    # 3. make_ics — календарь с экранированием и VALARM
    ev = [{"summary": "Тест, с запятой; и точкой", "date": "2026-09-06",
           "tzid": "Asia/Dushanbe", "alarms_min": [60]}]
    (tmp / "ev.json").write_text(json.dumps(ev, ensure_ascii=False), encoding="utf-8")
    code, _, _ = run("make_ics.py", tmp / "ev.json", tmp / "тест.ics")
    ics = (tmp / "тест.ics").read_text(encoding="utf-8")
    check("make_ics: валидный VCALENDAR + экранирование + VALARM",
          code == 0 and ics.startswith("BEGIN:VCALENDAR") and "Тест\\, с запятой\\;" in ics
          and "BEGIN:VALARM" in ics)

    # 4. make_checklist — HTML: чекбоксы, localStorage, озвучка, печать
    cl = {"title": "Т", "subtitle": "s", "storage_key": "t",
          "sections": [{"title": "Раздел", "items": ["раз", "два"]}]}
    (tmp / "cl.json").write_text(json.dumps(cl, ensure_ascii=False), encoding="utf-8")
    code, _, _ = run("make_checklist.py", tmp / "cl.json", tmp / "ч.html",
                     "--keep", tmp / "keep.txt")
    html = (tmp / "ч.html").read_text(encoding="utf-8")
    keep = (tmp / "keep.txt").read_text(encoding="utf-8")
    check("make_checklist: 2 чекбокса + speechSynthesis + localStorage + print",
          code == 0 and html.count('type="checkbox"') == 2 and "speechSynthesis" in html
          and "localStorage" in html and "@media print" in html)
    check("make_checklist --keep: раздел заглавными + пункты",
          "РАЗДЕЛ" in keep and "\nдва\n" in keep)

    # 5. read_program — эвристики на свободном тексте
    prog = ("День 1. Артуч (2200 м) — старт, 7 км\n"
            "День 2. Кемп Куликалон 2850 м (39.2551, 68.1723)\n"
            "Выезд 06.09.2026, финиш 16.09.2026")
    (tmp / "prog.txt").write_text(prog, encoding="utf-8")
    code, out, _ = run("read_program.py", tmp / "prog.txt")
    j = json.loads(out)
    pts = {p["name"]: p for p in j["points_draft"]}
    check("read_program: точки и координаты из текста",
          code == 0 and "Кемп Куликалон" in pts and pts["Кемп Куликалон"].get("lat") == 39.2551
          and "Артуч" in pts and pts["Артуч"].get("ele") == 2200)
    check("read_program: даты и дни", j["dates_iso"] == ["2026-09-06", "2026-09-16"]
          and j["days_mentioned"] == [1, 2])

    # 6. daylight — эталонные рассвет/закат (СТАТУС: 06.09 06:03/18:55) и новолуние 11–12.09
    (tmp / "pts.json").write_text(json.dumps(
        [{"name": "Куликалон", "lat": 39.2551, "lon": 68.1723, "ele": 2850}]), encoding="utf-8")
    code, out, _ = run("daylight.py", tmp / "pts.json", "--start", "2026-09-06", "--end", "2026-09-12")
    j = json.loads(out)
    d0 = j["days"][0]
    rise_min = int(d0["sunrise"].split(":")[0]) * 60 + int(d0["sunrise"].split(":")[1])
    check("daylight: рассвет 06.09 ≈ 06:03 (±10 мин)", abs(rise_min - 363) <= 10, d0["sunrise"])
    check("daylight: новолуние 11–12.09.2026",
          any(x["moon_phase"] == "Новолуние" and x["date"] in ("2026-09-11", "2026-09-12")
              for x in j["days"]))

    # 7. make_status — снимок проекта с диффом
    prj = tmp / "Маршрут"
    (prj / "входные").mkdir(parents=True)
    (prj / "входные" / "track.gpx").write_text("x", encoding="utf-8")
    code, _, _ = run("make_status.py", prj)
    status_files = list(prj.glob("СТАТУС_*.md"))
    check("make_status: файл-снимок создан", code == 0 and len(status_files) == 1)
    (prj / "входные" / "новое.txt").write_text("y", encoding="utf-8")
    run("make_status.py", prj)
    check("make_status: дифф ловит новые файлы",
          "Новые** (1)" in status_files[0].read_text(encoding="utf-8"))

    print(f"\n{'=' * 40}\nПройдено: {len(passed)}; упало: {len(failed)}")
    if failed:
        print("Падения:", *failed, sep="\n  ✗ ", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
