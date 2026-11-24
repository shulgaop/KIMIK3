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
import re
import subprocess
import sys
import time
from pathlib import Path

import edge_tts

try:
    import imageio_ffmpeg
except ImportError:  # проверка длительности отключится, размер останется
    imageio_ffmpeg = None

ГОЛОС = "ru-RU-DmitryNeural"  # D-008: мужской нейроголос для RU-аудиогида
ТЕМП = "-5%"                   # чуть медленнее разговорного — под трек
МИН_БАЙТ = 5_000               # меньше — считаем файл битым и перезаписываем
МИН_СЕК, МАКС_СЕК = 35, 130    # норма длительности трека по контракту выдачи
БЮДЖЕТ_МИН = 55                # общий лимит времени на запуск
ПАУЗА_ТРЕК = (15, 20)          # секунды между треками (анти-троттлинг)
ПАУЗА_ЦИКЛ = (100, 135)        # секунды между циклами повторов


def _длительность_сек(путь: Path) -> float | None:
    """Длительность mp3 по ffmpeg; None, если прочитать не удалось.

    Порог размера не ловит обрыв потока: edge-tts может отдать валидный
    mp3 на 22 с / 23 КБ (случай T-006, день 5 трек 06), поэтому готовность
    определяется длительностью, а не только весом файла.
    """
    if imageio_ffmpeg is None:
        return None
    out = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(путь)],
                         capture_output=True)
    найдено = re.search(rb"Duration: (\d+):(\d+):([\d.]+)", out.stderr)
    if not найдено:
        return None
    return (int(найдено.group(1)) * 3600 + int(найдено.group(2)) * 60
            + float(найдено.group(3)))


def _готов(путь: Path) -> bool:
    """Файл считается готовым, если он есть, не пустой и не оборван."""
    if not (путь.exists() and путь.stat().st_size >= МИН_БАЙТ):
        return False
    секунды = _длительность_сек(путь)
    if секунды is None:  # ffmpeg недоступен — доверяем размеру
        return imageio_ffmpeg is None
    return МИН_СЕК <= секунды <= МАКС_СЕК


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
        осталось = [п for п in план if not _готов(п[2])]
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
                if _готов(путь):
                    секунды = _длительность_сек(путь)
                    сводка = (f"{секунды:.0f} с, " if секунды else "")
                    print(f"  ✓ {имя} — {сводка}"
                          f"{путь.stat().st_size // 1024} КБ")
                else:  # обрыв потока: валидный mp3, но короче нормы
                    путь.unlink(missing_ok=True)
                    print(f"  ✗ {имя}: обрыв потока, файл удалён")
            time.sleep(random.uniform(*ПАУЗА_ТРЕК))

        прошло = (time.monotonic() - старт) / 60
        if прошло >= БЮДЖЕТ_МИН:
            недостающие = [п[0] for п in план if not _готов(п[2])]
            print(f"Бюджет {БЮДЖЕТ_МИН} мин исчерпан. "
                  f"Не озвучено: {len(недостающие)}: {недостающие}")
            sys.exit(2)
        пауза = random.uniform(*ПАУЗА_ЦИКЛ)
        print(f"Пауза {пауза:.0f} с перед следующим циклом "
              f"(прошло {прошло:.1f} мин).")
        time.sleep(пауза)


if __name__ == "__main__":
    main()
