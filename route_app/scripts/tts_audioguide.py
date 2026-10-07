#!/usr/bin/env python3
"""tts_audioguide.py — генерация аудиогида mp3 через edge-tts с контролем качества.

Использование:
  pip install edge-tts -i https://pypi.org/simple   # локальное зеркало может быть неполным!
  python3 tts_audioguide.py texts.json out_dir/ --voice ru-RU-DmitryNeural --rate -5%

texts.json: {"01 — Вводный": "текст с числами прописью...", "02 — Самарканд": "...", ...}

Правила текстов (см. инструкцию, раздел 7):
- ВСЕ числа прописью («четыре тысячи семьсот сорок метров», не «4740 м»).
- Аббревиатуры расписаны («джи-пи-эс»).
- 40–80 секунд ≈ 110–190 слов русского текста.
Контроль: после генерации ffprobe-проверка длительности каждого файла (ожидание 40–115 с,
для тематических треков допустимо до 120 с) и размера (>3 КБ). Сбойные — retry до 3 раз.
"""
import argparse, asyncio, json, subprocess, sys
from pathlib import Path


async def gen_one(text, voice, rate, path, retries=3):
    import edge_tts
    for attempt in range(1, retries + 1):
        try:
            await edge_tts.Communicate(text, voice, rate=rate).save(str(path))
            if path.stat().st_size > 3000:
                return True
        except Exception as e:
            print(f"  попытка {attempt}: {e}", file=sys.stderr)
            await asyncio.sleep(3 * attempt)
    return False


def probe_duration(path):
    """Длительность mp3 через ffprobe; None, если ffprobe не установлен."""
    import shutil
    if not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", str(path)], capture_output=True, text=True)
        return float(out.stdout.strip())
    except Exception:
        return None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("texts")
    ap.add_argument("outdir")
    ap.add_argument("--voice", default="ru-RU-DmitryNeural")
    ap.add_argument("--rate", default="-5%")
    args = ap.parse_args()

    texts = json.load(open(args.texts, encoding="utf-8"))
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    failed = []
    for name, text in texts.items():
        path = outdir / f"{name}.mp3"
        ok = await gen_one(text, args.voice, args.rate, path)
        if not ok:
            failed.append(name)
            continue
        dur = probe_duration(path)
        if dur is None:
            flag = "  (ffprobe не найден — длительность не проверена)"
            dur_s = "?"
        else:
            flag = "" if 35 <= dur <= 130 else "  ⚠️ длительность вне нормы!"
            dur_s = f"{dur:.0f}"
        print(f"✓ {name}.mp3 — {dur_s} с{flag}", file=sys.stderr)

    if failed:
        sys.exit(f"Не сгенерировались: {failed}")
    print(f"Готово: {len(texts)} треков в {outdir}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
