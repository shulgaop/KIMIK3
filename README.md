# Фанские горы · Кольцо Чимтарги — гид и генератор походных документов

Проект похода **Фанские горы, кольцо Чимтарги, 06–16.09.2026**: офлайн-гид
(HTML) и набор скриптов, генерирующих комплект документов похода
по программе, GPX-треку, билетам и датам.

## Структура

```
app/          Офлайн HTML-гид похода (одностраничные HTML-файлы,
              открываются без сервера и интернета)
              index.html — главная страница
route_app/    Генератор походных документов
              scripts/        Python-скрипты анализа GPX, KML, ICS, аудиогида
              ТЗ_*.md         Техническое задание (скоуп MVP)
              AGENTS.md       Инструкции для кодовых агентов (Kimi Code, Claude)
```

## Быстрый старт

Открыть гид: достаточно открыть `app/index.html` в браузере — ничего
собирать не нужно.

Скрипты (в `route_app/scripts/`):

```bash
python3 gpx_analyze.py    # анализ GPX-трека (км, высоты, профиль)
python3 make_kml.py       # генерация KML для Google Earth
python3 make_ics.py       # календарь похода (.ics)
python3 weather.py        # погодный движок: прогноз/климат/факт (Open-Meteo)
python3 make_status.py    # снимок проекта СТАТУС_<Маршрут>.md (F9)
python3 make_checklist.py # интерактивный чеклист HTML (F8)
python3 tts_audioguide.py # аудиогид (нужен piper и голос ru-RU-DmitryNeural)
```

## Работа с Kimi Code

1. Установите Kimi Code CLI: `curl -L code.kimi.com/install.sh | bash`
2. Клонируйте репозиторий и перейдите в папку.
3. Запустите `kimi`, выполните `/login` (аккаунт Kimi).
4. Команда `/init` сгенерирует `AGENTS.md` для проекта — в `route_app/`
   он уже есть и описывает контракт качества генерации документов.

## Публикация гида на GitHub Pages

В репозитории есть workflow `.github/workflows/pages.yml` — он публикует
папку `app/` на GitHub Pages при каждом пуше в `main`. Включите:
**Settings → Pages → Source: GitHub Actions**.
