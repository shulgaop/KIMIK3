"""Пакетная озвучка русского аудиогида (edge-tts, голос Дмитрий).

Читает `generated/slice-dayN/входные/texts.json` и пишет mp3 в
`generated/slice-dayN/выходные/аудио/<ключ>.mp3`. Тексты должны быть
предварительно размечены ударениями (`stress_audioguide.py`, D-008/D-012).

Сервис edge-tts периодически троттлит по IP (ошибка NoAudioReceived),
поэтому генерация идёт циклами с паузами: один проход по недостающим
трекам, пауза между треками, длинная пауза между циклами — до исчерпания
общего бюджета времени. Уже готовые файлы (размер больше порога)
пропускаются, поэтому скрипт безопасно перезапускать.

Запуск (из каталога routes/japan/data/):
    python tts_ru_audioguide.py 5 7
"""

import asyncio
import random
import sys
import time
from pathlib import Path

import edge_tts

ГОЛОС = "ru-RU-DmitryNeural"  # D-008: мужской нейроголос для RU-аудиогида
ТЕМП = "-5%"                   # чуть медленнее разговорного — под трек
МИН_БАЙТ = 5_000               # меньше — считаем файл битым и перезаписываем
БЮДЖЕТ_МИН = 55                # общий лимит времени на запуск
ПАУЗА_ТРЕК = (15, 20)          # секунды между треками (анти-троттлинг)
ПАУЗА_ЦИКЛ = (100, 135)        # секунды между циклами повторов


async def _озвучить(текст: str, путь: Path) -> None:
    """Один трек: потоковая запись mp3 от edge-tts."""
    поток = edge_tts.Communicate(текст, voice=ГОЛОС, rate=ТЕМП)
    with open(путь, "wb") as ф:
        async for кусок in поток.stream():
            if кусок["type"] == "audio":
                ф.write(кусок["data"])


def main() -> None:
    """Циклы повторов, пока все треки дней не будут озвучены."""
    дни = [int(а) for а in sys.argv[1:]] or [5, 7]
    корень = Path(__file__).resolve().parent.parent / "generated"

    план: list[tuple[str, str, Path]] = []
    for день in дни:
        срез = корень / f"slice-day{день}"
        import json
        треки = json.loads(
            (срез / "входные" / "texts.json").read_text(encoding="utf-8"))
        папка = срез / "выходные" / "аудио"
        папка.mkdir(parents=True, exist_ok=True)
        for имя, текст in треки.items():
            план.append((имя, текст, папка / f"{имя}.mp3"))

    старт = time.monotonic()
    цикл = 0
    while True:
        цикл += 1
        осталось = [п for п in план
                    if not (п[2].exists() and п[2].stat().st_size >= МИН_БАЙТ)]
        if not осталось:
            print("Все треки озвучены.")
            return
        print(f"--- цикл {цикл}: осталось {len(осталось)} из {len(план)} ---")
        for имя, текст, путь in осталось:
            try:
                asyncio.run(_озвучить(текст, путь))
            except Exception as ошибка:  # NoAudioReceived и сетевые сбои
                путь.unlink(missing_ok=True)
                print(f"  ✗ {имя}: {type(ошибка).__name__}")
            else:
                print(f"  ✓ {имя} — {путь.stat().st_size // 1024} КБ")
            time.sleep(random.uniform(*ПАУЗА_ТРЕК))

        прошло = (time.monotonic() - старт) / 60
        if прошло >= БЮДЖЕТ_МИН:
            недостающие = [п[0] for п in план
                           if not (п[2].exists()
                                   and п[2].stat().st_size >= МИН_БАЙТ)]
            print(f"Бюджет {БЮДЖЕТ_МИН} мин исчерпан. "
                  f"Не озвучено: {len(недостающие)}: {недостающие}")
            sys.exit(2)
        пауза = random.uniform(*ПАУЗА_ЦИКЛ)
        print(f"Пауза {пауза:.0f} с перед следующим циклом "
              f"(прошло {прошло:.1f} мин).")
        time.sleep(пауза)


if __name__ == "__main__":
    main()
