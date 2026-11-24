"""make_site.py — сборка публикуемой копии гида с парольным экраном (D-001).

Берёт комплект из `generated/`, добавляет входную страницу `index.html`
(экран кодового слова) и вставляет в каждый HTML сторожевой скрипт:
без отметки в localStorage страница перенаправляет на вход. Проверка —
SHA-256 кодового слова (Web Crypto API), пароль в открытом виде на сайте
не хранится. Защита «от случайных глаз», не криптография: прямые ссылки
на mp3/kml/ics не закрываются, личных данных в комплекте быть не должно.

Исходные файлы в `generated/` не изменяются — локальная работа остаётся
без экрана; сторожа живут только в публикуемой копии `site/`.

Запуск (из каталога routes/japan/data/):
    python make_site.py            # собрать routes/japan/site/
    python make_site.py --пароль СЛОВО   # сменить кодовое слово
"""

import argparse
import hashlib
import shutil
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent
ИСТОЧНИК = КОРЕНЬ / "generated"
ВЫХОД = КОРЕНЬ / "site"

ПАРОЛЬ_ПО_УМОЛЧАНИЮ = "кумано2027"  # выдано пользователю в чате T-007
КЛЮЧ_ХРАНИЛИЩА = "japanGate"        # имя отметки в localStorage

# То же оформление, что у дневных гидов (палитра васи/индиго/вермильон),
# чтобы экран входа не выбивался из комплекта.
ШАБЛОН_ВХОДА = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Япония 2027 — вход</title>
<style>
:root{{--paper:#f4efe3;--ink:#1c1a16;--ai:#1f3a5f;--shu:#b23a2a;--card:#fcfbf6;--line:#c9c0a8}}
*{{box-sizing:border-box}}
body{{background:var(--paper);color:var(--ink);font:16px/1.65 Georgia,"Times New Roman",serif;
     margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;
      box-shadow:0 1px 3px rgba(28,26,22,.08);padding:32px 28px;max-width:380px;width:100%}}
h1{{font-size:1.4rem;color:var(--ai);margin:0 0 4px;border-bottom:3px double var(--ai);padding-bottom:8px}}
.sub{{font-family:-apple-system,"Segoe UI",Roboto,sans-serif;font-size:.85rem;opacity:.75;margin:8px 0 20px}}
label{{display:block;font-family:-apple-system,"Segoe UI",Roboto,sans-serif;font-size:.85rem;
      color:var(--ai);margin-bottom:6px}}
input{{width:100%;padding:10px 12px;font-size:1rem;border:1px solid var(--line);border-radius:8px;
      background:var(--paper);color:var(--ink)}}
input:focus{{outline:2px solid var(--ai);outline-offset:1px}}
button{{width:100%;margin-top:14px;padding:11px;font-size:1rem;font-weight:600;color:#f8f5ec;
       background:var(--ai);border:none;border-radius:8px;cursor:pointer}}
button:hover{{background:var(--shu)}}
.err{{display:none;margin-top:12px;color:var(--shu);
     font-family:-apple-system,"Segoe UI",Roboto,sans-serif;font-size:.85rem}}
</style>
</head>
<body>
<form class="card" id="gate">
<h1>Япония 2027</h1>
<p class="sub">Фудзи и Кумано Кодо · приватный путеводитель</p>
<label for="word">Кодовое слово</label>
<input id="word" type="password" autocomplete="off" autofocus>
<button type="submit">Открыть гид</button>
<p class="err" id="err">Не подошло. Проверьте слово и попробуйте ещё раз.</p>
</form>
<script>
const HASH = "{хэш}";
const KEY = "{ключ}";
async function sha256(текст) {{
  const данные = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(текст));
  return [...new Uint8Array(данные)].map(b => b.toString(16).padStart(2, "0")).join("");
}}
document.getElementById("gate").addEventListener("submit", async (событие) => {{
  событие.preventDefault();
  const слово = document.getElementById("word").value.trim().toLowerCase();
  if (await sha256(слово) === HASH) {{
    localStorage.setItem(KEY, HASH);
    location.replace("Гид.html");
  }} else {{
    document.getElementById("err").style.display = "block";
    document.getElementById("word").select();
  }}
}});
if (localStorage.getItem(KEY) === HASH) location.replace("Гид.html");
</script>
</body>
</html>
"""

# Сторож: без отметки в localStorage — на вход. Выполняется до отрисовки,
# поэтому содержимое страницы не «вспыхивает» для посторонних.
ШАБЛОН_СТОРОЖА = (
    '<script>(function(){{try{{if(localStorage.getItem("{ключ}")'
    '==="{хэш}")return;}}catch(e){{}}location.replace("{путь}");}})();</script>'
)


def собрать(пароль: str) -> None:
    """Копирует комплект в site/, добавляет вход и сторожей."""
    хэш = hashlib.sha256(пароль.lower().encode()).hexdigest()
    if ВЫХОД.exists():
        shutil.rmtree(ВЫХОД)
    ВЫХОД.mkdir()

    for источник in ИСТОЧНИК.rglob("*"):
        относительный = источник.relative_to(ИСТОЧНИК)
        цель = ВЫХОД / относительный
        if источник.is_dir():
            цель.mkdir(exist_ok=True)
            continue
        if источник.suffix == ".md":  # исходники гидов на сайте не нужны
            continue
        if источник.suffix == ".html":
            глубина = len(относительный.parent.parts)
            путь_ко_входу = "/".join([".."] * глубина + ["index.html"])
            сторож = ШАБЛОН_СТОРОЖА.format(
                ключ=КЛЮЧ_ХРАНИЛИЩА, хэш=хэш, путь=путь_ко_входу)
            текст = источник.read_text(encoding="utf-8")
            if "<head>" not in текст:
                raise ValueError(f"нет <head> в {источник}")
            текст = текст.replace("<head>", "<head>\n" + сторож, 1)
            цель.write_text(текст, encoding="utf-8")
        else:
            shutil.copy2(источник, цель)

    (ВЫХОД / "index.html").write_text(
        ШАБЛОН_ВХОДА.format(хэш=хэш, ключ=КЛЮЧ_ХРАНИЛИЩА), encoding="utf-8")
    (ВЫХОД / ".nojekyll").touch()  # иначе Pages прогоняет Jekyll
    файлов = sum(1 for п in ВЫХОД.rglob("*") if п.is_file())
    print(f"✓ {ВЫХОД}: {файлов} файлов, экран входа + сторожа, "
          f"пароль «{пароль}»")


def main() -> None:
    """Разбор аргументов, манифест и сборка."""
    разбор = argparse.ArgumentParser()
    разбор.add_argument("--пароль", default=ПАРОЛЬ_ПО_УМОЛЧАНИЮ)
    аргументы = разбор.parse_args()
    # Манифест генерируем ДО копирования: гид.json должен попасть в site/.
    try:
        import make_manifest
        make_manifest.main()
    except Exception as ошибка:  # манифест — надстройка, сайт важнее
        print(f"⚠ манифест не собран: {ошибка}")
    собрать(аргументы.пароль)


if __name__ == "__main__":
    main()
