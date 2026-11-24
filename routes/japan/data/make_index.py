"""make_index.py — сводная стартовая страница комплекта «Япония 2027».

Собирает `generated/Гид.html`: оглавление всех девяти дней со ссылками на
срезы и ссылки на комплектные файлы (KML, ICS, чеклист, бюджет,
бронирования). Страница самодостаточная и офлайн, в той же палитре, что и
дневные гиды (CSS импортируется из `route_app/scripts/make_guide_html.py`,
чтобы стили не расходились).

Запуск (из каталога routes/japan/data/):
    python make_index.py
"""

import importlib.util
import json
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent
СКРИПТЫ_ДВИЖКА = КОРЕНЬ.parent.parent / "route_app" / "scripts"

# Дополнительные стили только для карточек оглавления; базовая палитра — из
# движка, чтобы стартовая страница и дневные гиды выглядели одним комплектом.
CSS_КАРТОЧКИ = """
.days{list-style:none;padding:0;margin:16px 0}
.days li{background:var(--card);border:1px solid var(--line);border-radius:10px;
         padding:12px 16px;margin:10px 0;box-shadow:0 1px 3px rgba(28,26,22,.08)}
.days a{display:block;color:var(--ai);font-weight:600;text-decoration:none;font-size:1.02rem}
.days a:hover{color:var(--shu)}
.days .meta{font-family:-apple-system,"Segoe UI",Roboto,sans-serif;font-size:.85rem;
            color:var(--ink);opacity:.75;margin-top:2px}
.kit td:first-child{white-space:nowrap;font-weight:600;color:var(--ai)}
header .sub{font-family:-apple-system,"Segoe UI",Roboto,sans-serif;font-size:.92rem;
            opacity:.8;margin:-12px 0 18px}
"""


def _css_движка() -> str:
    """Импортирует CSS из make_guide_html.py без запуска модуля."""
    spec = importlib.util.spec_from_file_location(
        "make_guide_html", СКРИПТЫ_ДВИЖКА / "make_guide_html.py")
    модуль = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("make_guide_html", модуль)
    spec.loader.exec_module(модуль)
    return модуль.CSS


def _день_из_среза(номер: int) -> dict[str, str] | None:
    """Карточка дня из готового среза без записи в days.json.

    День 6 — утверждённый ручной срез (T-005), его контент не дублируется
    в days.json; заголовок и дату берём из самого Гид.md, чтобы оглавление
    не расходилось с содержимым.
    """
    гид = КОРЕНЬ / "generated" / f"slice-day{номер}" / "выходные" / "Гид.md"
    if not гид.is_file():
        return None
    текст = гид.read_text(encoding="utf-8")
    заголовок = текст.splitlines()[0].lstrip("# ").strip()
    дата = ""
    for строка in текст.splitlines()[1:12]:
        if "**Дата:**" in строка:
            дата = строка.split("**Дата:**", 1)[1].split("·")[0].strip()
            break
    return {"title": заголовок, "date_human": дата, "leg": ""}


def main() -> None:
    """Читает config/days.json и пишет generated/Гид.html."""
    дни: dict[str, dict] = json.loads(
        (КОРЕНЬ / "config" / "days.json").read_text(encoding="utf-8"))
    for номер in range(1, 10):
        if str(номер) not in дни:
            срез = _день_из_среза(номер)
            if срез:
                дни[str(номер)] = срез

    строки_дней = []
    for номер in sorted(дни, key=int):
        cfg = дни[номер]
        ссылка = f"slice-day{номер}/выходные/Гид.html"
        мета = cfg.get("date_human", "")
        if cfg.get("leg"):
            мета += f" · {cfg['leg']}"
        строки_дней.append(
            f'<li><a href="{ссылка}">{cfg["title"]}</a>'
            f'<div class="meta">{мета}</div></li>')

    комплект = [
        ("Карта маршрута (KML)", "маршрут.kml",
         "Импорт в Organic Maps / MAPS.ME: 4 трека и все ключевые точки"),
        ("Календарь (ICS)", "маршрут.ics",
         "9 событий с временем по Asia/Tokyo — импорт в календарь телефона"),
        ("Чеклист", "Чеклист.html",
         "38 пунктов: документы, снаряжение, брони, на тропу"),
        ("Бюджет", "Бюджет.html",
         "Расчёт кодом по живому курсу EUR→JPY; итог в пределах €1500"),
        ("Бронирования", "Бронирования.html",
         "14 позиций со сроками и кликабельными ссылками; статусы обновляются"),
        ("Источники", "Источники.html",
         "Официальные сайты, карты, билеты, статьи и видео, на которых построен гид"),
    ]
    строки_комплекта = "".join(
        f'<tr><td><a href="{href}">{имя}</a></td><td>{описание}</td></tr>'
        for имя, href, описание in комплект)

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Япония 2027 · Фудзи и Кумано Кодо — путеводитель</title>
<style>{_css_движка()}{CSS_КАРТОЧКИ}</style>
</head>
<body>
<div class="wrap">
<header>
<h1>Япония 2027 · Фудзи и Кумано Кодо</h1>
<p class="sub">2–10 сентября 2027 · 9 дней · пеший формат · пояс Asia/Tokyo</p>
</header>

<nav><b>Как пользоваться</b>
<a>Все страницы самодостаточные и работают офлайн — откройте нужный день
заранее, и он останется доступен без сети. Русский аудиогид (день 2 и дни 5–7)
лежит в папке <code>аудио/</code> рядом с гидом дня и запускается по ссылкам
из таблицы «Аудиогид дня». KML импортируется в офлайн-карты, ICS — в
календарь.</a>
</nav>

<h2>Дни маршрута</h2>
<ul class="days">
{chr(10).join(строки_дней)}
</ul>

<h2>Комплект маршрута</h2>
<table class="kit">
<tr><th>Файл</th><th>Что внутри</th></tr>
{строки_комплекта}
</table>

<p><em>Собрано кодом (<code>make_index.py</code>) из
<code>config/days.json</code>. Брони и расписания 2027 года помечены
«ожидается» и перепроверяются по мере публикации официальных данных.</em></p>
</div>
</body>
</html>
"""
    выход = КОРЕНЬ / "generated" / "Гид.html"
    выход.write_text(html + "\n", encoding="utf-8")
    print(f"✓ {выход}: {len(html)} символов, офлайн")


if __name__ == "__main__":
    main()
