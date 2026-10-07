#!/usr/bin/env python3
"""llm.py — LLM-слой через OpenRouter (F4: генерация гида и др.).

OpenRouter — единая точка доступа к моделям (OpenAI-совместимый API).
Бесплатные модели имеют суффикс «:free»; платные доступны по тому же ключу
(тарификация аккаунта пользователя на openrouter.ai).

Ключ: переменная окружения OPENROUTER_API_KEY или файл learn/llm_config.json
(создаётся мастером; learn/ в .gitignore — ключ не коммитится).

Использование:
  python3 llm.py models                          # список бесплатных моделей
  python3 llm.py guide projects/<маршрут>        # сгенерировать Гид.md
  python3 llm.py guide projects/<маршрут> --model openai/gpt-5 --key sk-or-...

Выбор бесплатной модели по умолчанию: первая доступная из предпочтительного
списка (крупный контекст, сильная модель); список всегда можно обновить
командой `models`.
"""
import argparse, json, os, re, sys, time, urllib.request
from pathlib import Path

API = "https://openrouter.ai/api/v1"
CONFIG = Path(__file__).parent.parent / "learn" / "llm_config.json"

# предпочтение бесплатных: сначала самые сильные/современные с большим контекстом
FREE_PREFERENCE = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "thinkingmachines/inkling:free",
]

GUIDE_SYSTEM = """Ты — опытный руководитель горных походов и автор путеводителей.
Пишешь MD-путеводитель по горному маршруту по данным проекта.

Жёсткие правила (нарушать нельзя):
- Все числа (км, высоты, уклоны, азимуты) — ТОЛЬКО из присланного анализа трека;
  ничего не вычисляй и не выдумывай сам. Карточный километраж программы занижен
  на 10–20 % — давай «по GPS / по программе», где есть оба.
- Погода — строго из присланного блока; если там климатические нормы, пиши
  «климат, перепроверить <дата>», прогноз не выдумывай.
- Факты (история, география, природа) пиши только в общедоступно известных
  пределах; сомнительное помечай «по отзывам/по преданию».
- Структура гида: 1) шапка (маршрут, даты, км, высоты, перевалы);
  2) логистика; 3) погода/ветер/высоты с таблицей по ночёвкам; 4) характер троп
  (таблица: поверхность | набор м/км | макс. уклон | сложность); 5) маршрут
  по дням (чипы: км, набор/сброс, азимут, ночёвка; ход дня; факт-блоки;
  «Ночёвка», «Вода», «Опасности дня»); 6) сводная таблица точек с координатами;
  7) опасности и аварийные сходы; 8) снаряжение — акценты под маршрут;
  9) источники. Правило тайминга: перевалы до 13:00–14:00, ключевой — выход
  5:00–6:00. Ночёвки выше 3500 м — пометить про акклиматизацию.
- Язык — русский, стиль — полевой журнал: конкретно, без воды.
"""


def load_config():
    if CONFIG.is_file():
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    return {}


def save_config(cfg):
    CONFIG.parent.mkdir(exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def get_key(cli_key=None):
    key = cli_key or os.environ.get("OPENROUTER_API_KEY") or load_config().get("api_key")
    if not key:
        sys.exit("⚠️  Нет ключа OpenRouter: задайте OPENROUTER_API_KEY, --key "
                 "или сохраните ключ в мастере (шаг «Гид»). Ключ бесплатный: openrouter.ai/keys")
    return key


def _post(path, payload, key, timeout=300):
    req = urllib.request.Request(API + path, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://github.com/shulgaop/KIMIK3",
                 "X-Title": "Route Guide Generator"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        if e.code == 401:
            sys.exit("⚠️  Ключ OpenRouter отклонён (401) — проверьте ключ в шаге «Гид»")
        if e.code >= 500:
            raise RuntimeError(f"HTTP {e.code}: {body[:150]}")
        sys.exit(f"⚠️  OpenRouter HTTP {e.code}: {body}")


def chat(messages, model, key, max_tokens=16000, temperature=0.4):
    """Один запрос chat/completions с ретраями на сетевые сбои."""
    payload = {"model": model, "messages": messages,
               "max_tokens": max_tokens, "temperature": temperature}
    last = None
    for attempt, pause in enumerate((5, 15), start=1):
        try:
            r = _post("/chat/completions", payload, key)
        except (urllib.error.URLError, OSError) as e:  # URLError, обрывы TLS/соединения
            last = e
            print(f"⚠️  {e} — повтор через {pause} с", file=sys.stderr)
            time.sleep(pause)
            continue
        if "error" in r:  # OpenRouter отвечает 200 с объектом error (напр. провайдер перегружен)
            raise RuntimeError(f"{model}: {r['error'].get('message', r['error'])}")
        return r["choices"][0]["message"]["content"]
    sys.exit(f"⚠️  Сеть недоступна: {last}")


def candidate_models(preferred=None, key=None):
    """Очередь моделей: явно заданная (без фолбэка) или free-предпочтения по живому списку."""
    if preferred:
        return [preferred]
    try:
        ids = [m["id"] for m in list_free_models(key)]
    except Exception:
        ids = []
    chain = [m for m in FREE_PREFERENCE if m in ids] or ids[:3] or FREE_PREFERENCE
    return chain


def list_free_models(key=None):
    """Живой список бесплатных моделей OpenRouter (ключ не нужен)."""
    with urllib.request.urlopen(API + "/models", timeout=30) as r:
        data = json.load(r)["data"]
    free = [{"id": m["id"], "context": m.get("context_length", 0)}
            for m in data if m["id"].endswith(":free")]
    return sorted(free, key=lambda m: -m["context"])


def default_model(key=None):
    """Самая предпочтительная из доступных бесплатных моделей."""
    ids = {m["id"] for m in list_free_models(key)}
    for m in FREE_PREFERENCE:
        if m in ids:
            return m
    return sorted(ids)[0] if ids else FREE_PREFERENCE[0]


def build_guide_context(project):
    """Контекст генерации из файлов проекта + обучающих материалов."""
    project = Path(project)
    in_d, out_d = project / "входные", project / "выходные"
    parts = []

    def add(title, path, limit=30000):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")[:limit]
            parts.append(f"## {title}\n{text}")

    add("Программа похода (свободный текст)", in_d / "программа.txt")
    add("Точки маршрута (points.json)", in_d / "points.json")
    add("Анализ трека (анализ.json — ВСЕ числа брать отсюда)", out_d / "анализ.json")
    add("Погода (Погода.md)", out_d / "Погода.md")
    add("Факты из открытых источников (Факты.md — Википедия/OSM, использовать "
        "для факт-блоков: история, география, флора, фауна, культура)",
        out_d / "Факты.md", limit=25000)
    add("Фотометки (фотометки.json)", out_d / "фотометки.json", limit=5000)

    learn = Path(__file__).parent.parent / "learn"
    add("Правила генерации (learn/правила.md)", learn / "правила.md", limit=8000)
    if (learn / "примеры.json").is_file():
        ex = json.loads((learn / "примеры.json").read_text(encoding="utf-8"))[:5]
        if ex:
            parts.append("## Эталонные примеры оформления\n" +
                         "\n\n".join(f"### {e.get('title', '')}\n{e.get('output', '')[:2000]}"
                                     for e in ex))
    return "\n\n".join(parts)


def chat_with_fallback(messages, explicit_model, key, max_tokens=16000):
    """Запрос с перебором бесплатных моделей (провайдеры бывают перегружены).
    Возвращает (текст, использованная_модель)."""
    last_err = None
    for m in candidate_models(explicit_model, key):
        try:
            print(f"Модель: {m}", file=sys.stderr)
            return chat(messages, m, key, max_tokens=max_tokens), m
        except RuntimeError as e:
            last_err = e
            print(f"⚠️  {e} — пробую следующую бесплатную модель", file=sys.stderr)
    sys.exit(f"⚠️  Доступные модели не ответили. Последняя ошибка: {last_err}")


def generate_guide(project, model=None, key=None, out_name="Гид.md"):
    """Генерация MD-гида проекта → выходные/Гид.md. Возвращает путь."""
    project = Path(project)
    key = get_key(key)
    explicit = model or load_config().get("model")
    context = build_guide_context(project)
    if not context.strip():
        sys.exit("⚠️  В проекте нет данных: пройдите шаги «Программа», «Анализ», «Погода»")
    user = (f"Проект: {project.name}\n\n{context}\n\n"
            "Напиши полный путеводитель по правилам из system-промпта.")
    print(f"Контекст {len(context)} символов", file=sys.stderr)
    text, _ = chat_with_fallback([{"role": "system", "content": GUIDE_SYSTEM},
                                  {"role": "user", "content": user}], explicit, key)
    out = project / "выходные" / out_name
    out.parent.mkdir(exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"✓ {out}: {len(text)} символов", file=sys.stderr)
    return out


AUDIO_SYSTEM = """Ты — автор аудиогидов для горных походов. Пишешь тексты для озвучки (TTS).

Жёсткие правила (нарушать нельзя):
- ВСЕ числа — прописью («четыре тысячи семьсот сорок метров», не «4740 м»);
  аббревиатуры расписаны («джи-пи-эс»); знаки словами («плюс пять градусов»).
- 110–190 слов на трек (это 40–80 секунд звучания).
- Живой рассказ от второго лица («Ты выходишь к озеру…», «Справа — стена цирка…»),
  тон — проводник рядом, не учебник.
- На точку: 1 исторический факт + 1 географический + 1 природный/культурный +
  1 практический совет. Числа и высоты — только из присланных данных.
- Структура: трек «01 — Вводный» (обзор: даты, километраж, высоты, главные
  правила безопасности), далее по одному треку на день/точку маршрута,
  финальный трек — с поздравлением.
- ОТВЕТ — СТРОГО валидный JSON без markdown-ограждений и пояснений:
  {"01 — Вводный": "текст...", "02 — Название точки": "текст...", ...}
"""


def generate_audio_texts(project, model=None, key=None, out_name="аудиотексты.json"):
    """Тексты аудиогида (формат tts_audioguide.py) → выходные/аудиотексты.json."""
    project = Path(project)
    key = get_key(key)
    explicit = model or load_config().get("model")
    context = build_guide_context(project)
    guide = project / "выходные" / "Гид.md"
    if guide.is_file():
        context += "\n\n## Путеводитель (Гид.md)\n" + \
                   guide.read_text(encoding="utf-8", errors="replace")[:20000]
    if not context.strip():
        sys.exit("⚠️  В проекте нет данных: пройдите шаги «Программа», «Анализ», «Погода»")
    messages = [{"role": "system", "content": AUDIO_SYSTEM},
                {"role": "user", "content":
                 f"Проект: {project.name}\n\n{context}\n\n"
                 "Составь тексты аудиогида (8–14 треков) и верни строго JSON."}]
    text = None
    for attempt in (1, 2):  # вторая попытка — просим починить JSON
        raw, _ = chat_with_fallback(messages, explicit, key, max_tokens=12000)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        try:
            texts = json.loads(raw)
            break
        except json.JSONDecodeError as e:
            print(f"⚠️  Модель вернула невалидный JSON ({e}) — повтор", file=sys.stderr)
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": "Верни только валидный JSON, без пояснений."})
    else:
        sys.exit("⚠️  Модель дважды вернула невалидный JSON — попробуйте другую модель")

    bad_keys = [k for k in texts if not re.match(r"^\d{2}\s+—\s+", k)]
    if bad_keys:
        print(f"⚠️  Ключи без нумерации «NN — »: {bad_keys}", file=sys.stderr)
    for k, v in texts.items():
        words = len(str(v).split())
        if not 80 <= words <= 220:
            print(f"⚠️  «{k}»: {words} слов (норма 110–190)", file=sys.stderr)

    out = project / "выходные" / out_name
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(texts, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"✓ {out}: {len(texts)} треков", file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["models", "guide", "audio"])
    ap.add_argument("project", nargs="?")
    ap.add_argument("--model", help="id модели OpenRouter (платные — тоже, по вашему ключу)")
    ap.add_argument("--key", help="ключ OpenRouter (или OPENROUTER_API_KEY / мастер)")
    args = ap.parse_args()

    if args.cmd == "models":
        free = list_free_models()
        print(f"Бесплатных моделей: {len(free)}. По умолчанию: {default_model()}")
        for m in free:
            print(f"  {m['id']}  (контекст {m['context'] // 1024}K)")
    else:
        if not args.project:
            sys.exit(f"Укажите папку проекта: llm.py {args.cmd} projects/<маршрут>")
        if args.cmd == "guide":
            generate_guide(args.project, model=args.model, key=args.key)
        else:
            generate_audio_texts(args.project, model=args.model, key=args.key)


if __name__ == "__main__":
    main()
