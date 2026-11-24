"""make_manifest.py — машиночитаемый манифест гида для интеграций.

Приложения (Track Fourge и др.) читают `гид.json` с опубликованного URL
и получают структуру комплекта без разбора HTML: дни, страницы, аудио,
файлы. Манифест не содержит личных данных; как и mp3, он доступен по
прямой ссылке без парольного экрана (экран — «от случайных глаз», D-001).

Только stdlib — скрипт запускается в CI (GitHub Actions, setup-python
без зависимостей) из `make_site.py` после сборки site/.

Запуск (из каталога routes/japan/data/):
    python make_manifest.py
"""

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent
СГЕНЕРИРОВАНО = КОРЕНЬ / "generated"
КОНФИГ = КОРЕНЬ / "config" / "days.json"
ВЫХОД = СГЕНЕРИРОВАНО / "гид.json"

ИД_ГИДА = "japan-2027"
НАЗВАНИЕ = "Япония 2027 · Фудзи и Кумано Кодо"
ДАТЫ = {"start": "2027-09-02", "end": "2027-09-10", "tz": "Asia/Tokyo"}

# Файлы комплекта верхнего уровня: ключ -> (имя файла, описание для приложения)
КОМПЛЕКТ = {
    "kml": ("маршрут.kml", "треки и точки для офлайн-карт"),
    "ics": ("маршрут.ics", "события календаря Asia/Tokyo"),
    "checklist": ("Чеклист.html", "38 пунктов сбора"),
    "budget": ("Бюджет.html", "расчёт бюджета EUR/JPY"),
    "bookings": ("Бронирования.html", "14 позиций со ссылками бронирования"),
    "sources": ("Источники.html", "источники и ссылки гида"),
}


def _коммит() -> str | None:
    """Короткий sha текущего HEAD; None вне git-окружения."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=КОРЕНЬ, timeout=10)
        return out.stdout.strip() or None
    except Exception:  # git недоступен (архив, копия) — не критично
        return None


def _заголовок_дня(гид_md: Path) -> str | None:
    """Первая строка '# …' из Гид.md дня как заголовок."""
    if not гид_md.is_file():
        return None
    первая = гид_md.read_text(encoding="utf-8").splitlines()[0]
    return первая.lstrip("# ").strip() or None


def _дни() -> list[dict]:
    """Список дней из срезов: номер, заголовок, страница, треки аудио."""
    конфиг = json.loads(КОНФИГ.read_text(encoding="utf-8")) \
        if КОНФИГ.is_file() else {}
    дни = []
    for срез in sorted(СГЕНЕРИРОВАНО.glob("slice-day*")):
        номер = int(срез.name.removeprefix("slice-day"))
        страница = срез / "выходные" / "Гид.html"
        if not страница.is_file():
            continue
        заголовок = (конфиг.get(str(номер), {}).get("title")
                     or _заголовок_дня(срез / "выходные" / "Гид.md"))
        аудио = []
        папка_аудио = срез / "выходные" / "аудио"
        if папка_аудио.is_dir():
            for mp3 in sorted(папка_аудио.glob("*.mp3")):
                # Имя файла «NN — Название.mp3» — берём название без номера.
                название = re.sub(r"^\d+ — ", "", mp3.stem)
                аудио.append({
                    "title": название,
                    "file": str(mp3.relative_to(СГЕНЕРИРОВАНО)).replace("\\", "/"),
                    "bytes": mp3.stat().st_size,
                })
        дни.append({
            "day": номер,
            "title": заголовок,
            "page": str(страница.relative_to(СГЕНЕРИРОВАНО)).replace("\\", "/"),
            "audio": аудио,
        })
    return дни


def main() -> None:
    """Собирает манифест и пишет generated/гид.json."""
    манифест = {
        "schema": "kimik3-guide-manifest/1",
        "id": ИД_ГИДА,
        "title": НАЗВАНИЕ,
        "dates": ДАТЫ,
        "entry": "Гид.html",
        "gate": {
            "type": "sha256-localstorage",
            "note": "экран кодового слова; слово — в приватном репозитории, "
                    "приложению не передаётся",
        },
        "days": _дни(),
        "files": {ключ: {"file": имя, "title": описание}
                  for ключ, (имя, описание) in КОМПЛЕКТ.items()
                  if (СГЕНЕРИРОВАНО / имя).is_file()},
        "build": {
            "commit": _коммит(),
            "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }
    ВЫХОД.write_text(
        json.dumps(манифест, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    треков = sum(len(д["audio"]) for д in манифест["days"])
    print(f"✓ {ВЫХОД}: дней {len(манифест['days'])}, "
          f"аудиотреков {треков}, файлов комплекта {len(манифест['files'])}")


if __name__ == "__main__":
    main()
