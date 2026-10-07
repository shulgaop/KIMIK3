#!/usr/bin/env python3
"""first_aid.py — модуль «Аптечка»: чеклист медикаментов + напоминания о приёме.

По профилю маршрута (высоты точек points.json, даты) генерирует:
- аптечка_чеклист.json — формат make_checklist.py (разделы: врач/рецепты,
  без рецепта, перевязка и уход, правила высоты);
- аптечка_напоминания.json — формат make_ics.py: ежедневный приём каждое утро
  похода + старт профилактики горной болезни за 1 день до первой точки ≥3500 м
  (порядок точек считается дневным: i-я точка ≈ i-й день от --start).

⚠️ Дисклеймер честности: это НЕ медицинская рекомендация. Списки — шаблон
по эталону Фанов; рецептурные препараты и дозы — только по назначению врача.
Это явно написано в каждом выходном файле.

Использование:
  python3 first_aid.py points.json --start 2026-09-06 --end 2026-09-16 \
      --tz Asia/Dushanbe --out выходные/
"""
import argparse, json, sys
from datetime import date, timedelta
from pathlib import Path

DISCLAIMER = ("Не медицинская рекомендация: шаблон по эталону «Фанские горы». "
              "Рецептурные препараты и дозы — только по назначению врача.")

BASE_ITEMS = [  # безрецептурная база (по эталону Фанов)
    ("Ибупрофен 400 мг ×10–20", "боль: головная (в т.ч. высотная), мышечная"),
    ("Парацетамол 500 мг ×10", "жар, боль, если нельзя НПВС"),
    ("Лоперамид ×10", "диарея (стоп-симптом)"),
    ("Нифуроксазид 200 мг ×8–12", "кишечная инфекция"),
    ("Смекта ×6 пакетиков", "желудок, отравление"),
    ("Цетиризин 10 мг ×10", "аллергия, укусы"),
    ("Пастилки от горла ×6–10", "горло на холодном ветру"),
    ("Изотоник/регидрон ×10", "обезвоживание: при диарее + соль и сахар"),
]
CARE_ITEMS = [
    ("Повидон-йод (антисептик) 30 мл", "раны, ссадины, место укуса клеща"),
    ("Лейкопластырь рулонный 5×500 см", "«горячие точки», фиксация повязок"),
    ("Стик от натирания", "профилактика мозолей — каждое утро ДО носков"),
    ("Пантенол мини", "ожоги, обветривание"),
    ("Гигиеническая помада SPF 50+", "губы: УФ +10–12 % на км высоты"),
    ("Вазелин мини", "губы/нос/лицо от ветра, стопы от натирания"),
    ("Искусственная слеза 10 мл", "глаза: сухость, пыль, УФ"),
    ("Солевой спрей для носа", "сухость слизистой на высоте"),
    ("Перчатки мед. + малые ножницы + пинцет", "обработка ран, клещи"),
]
ALTITUDE_ITEMS = [  # добавляются при ночёвках/перевалах ≥ 3500 м
    ("Ацетазоламид (Диакарб) 250 мг", "профилактика горной болезни — по назначению врача"),
    ("Дексаметазон 0,5 мг ×20", "ударная терапия горной болезни — по назначению врача"),
    ("Милдронат 500 мг ×10–20", "начать за 3–4 дня до высотной части — по назначению врача"),
]
DOCTOR_ITEMS = [
    ("Визит к врачу: рецепты и дозы", "диакарб, дексаметазон, антибиотик (азитромицин)"),
    ("Личные ежедневные препараты", "на каждый день + запас на 3 дня — в НЕСКОЛЬКИХ местах"),
    ("Аллергокарта", "на что аллергия — записать и показать гиду"),
]
ALTITUDE_RULES = [
    "Головная боль + тошнота/слабость — не подниматься выше; не проходит — спуск. Лечение горной болезни — спуск.",
    "Пить 3–4 л/день; моча светлая = достаточно.",
    "Ночёвки выше 3500 м — только после акклиматизации (правило «пилы»).",
    "Бисопролол и подобные маскируют пульс — ориентир по самочувствию, не по ЧСС.",
    "Диакарб даёт мочегонный эффект и парестезии — это нормально; не сочетать с аспирином.",
]


def build_checklist(max_ele):
    """Чеклист аптечки в формате make_checklist.py."""
    sections = [
        {"title": "Врач и рецепты (до похода)",
         "items": [f"{n} — {d}" for n, d in DOCTOR_ITEMS],
         "note": DISCLAIMER},
        {"title": "Лекарства (без рецепта)",
         "items": [f"{n} — {d}" for n, d in BASE_ITEMS]},
        {"title": "Перевязка и уход",
         "items": [f"{n} — {d}" for n, d in CARE_ITEMS]},
    ]
    if max_ele >= 3500:
        sections.insert(1, {"title": "Высотный блок (≥3500 м)",
                            "items": [f"{n} — {d}" for n, d in ALTITUDE_ITEMS],
                            "note": "Ночёвки/перевалы выше 3500 м на маршруте есть."})
        sections.append({"title": "Правила высоты", "items": ALTITUDE_RULES})
    return {"title": "Аптечка · поход", "subtitle": DISCLAIMER,
            "storage_key": "firstAidChecklist", "sections": sections}


def build_reminders(points, start, end, tzid):
    """События-напоминания (формат make_ics.py): ежедневный приём + старт профилактики."""
    events = []
    d = start
    while d <= end:  # ежедневный приём личных препаратов, каждое утро похода
        events.append({"summary": "💊 Лекарства (ежедневные, по назначению врача)",
                       "start": f"{d.isoformat()}T07:00:00", "end": f"{d.isoformat()}T07:15:00",
                       "tzid": tzid, "alarms_min": [0]})
        d += timedelta(days=1)
    # первая точка ≥3500 м → профилактика горняшки за 1 день (порядок точек ≈ дни)
    for i, p in enumerate(points):
        if (p.get("ele") or 0) >= 3500:
            day = start + timedelta(days=max(i - 1, 0))
            if day < start:
                day = start
            events.append({
                "summary": "💊 Старт профилактики горной болезни (по назначению врача)",
                "start": f"{day.isoformat()}T08:00:00", "end": f"{day.isoformat()}T08:15:00",
                "tzid": tzid,
                "description": f"Первая высокая точка «{p['name']}» ({p['ele']} м) — "
                               f"ориентировочно день {i + 1}. " + DISCLAIMER,
                "alarms_min": [720, 60]})
            break
    return events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("points", help="points.json маршрута (ele у точек)")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--tz", default="Asia/Dushanbe", help="пояс IANA для напоминаний")
    ap.add_argument("--out", required=True, help="папка результата")
    args = ap.parse_args()

    points = json.load(open(args.points, encoding="utf-8"))
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    max_ele = max((p.get("ele") or 0) for p in points)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cl = build_checklist(max_ele)
    (out / "аптечка_чеклист.json").write_text(
        json.dumps(cl, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ev = build_reminders(points, start, end, args.tz)
    (out / "аптечка_напоминания.json").write_text(
        json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    high = max_ele >= 3500
    print(f"✓ аптечка_чеклист.json ({sum(len(s['items']) for s in cl['sections'])} пунктов"
          f"{', +высотный блок' if high else ''}) и аптечка_напоминания.json "
          f"({len(ev)} событий)", file=sys.stderr)
    if not high:
        print("Ночёвок ≥3500 м нет — высотный блок не добавлен", file=sys.stderr)


if __name__ == "__main__":
    main()
