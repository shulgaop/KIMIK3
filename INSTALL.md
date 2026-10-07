# INSTALL.md — установка и запуск

Приложение «Генератор путеводителей горных походов» (KIMIK3):
офлайн HTML-гид (`app/`, не требует установки) + мастер генерации маршрутов
(`route_app/webapp.py`, локальный веб-интерфейс).

## 1. Что понадобится

- **Python 3.10 или новее** (проверено на 3.12–3.14);
- **Git**;
- ~200 МБ свободного места;
- интернет — только для установки и для шага «Погода» (Open-Meteo, бесплатно,
  без ключей). Сами документы генерируются офлайн.

Опционально (только для аудиогида): `pip install edge-tts`.

---

## 2. Windows 11

1. **Python:** https://www.python.org/downloads/ → «Download Python 3.x».
   При установке **обязательно** поставьте галочку **«Add python.exe to PATH»**.
   Проверка (Win+R → `cmd`):
   ```cmd
   python --version
   ```
2. **Git:** https://git-scm.com/download/win → установка с настройками по умолчанию.
3. **Скачать проект** (в командной строке):
   ```cmd
   cd %USERPROFILE%\Documents
   git clone https://github.com/shulgaop/KIMIK3.git
   cd KIMIK3\route_app
   ```
4. **Виртуальное окружение и зависимости:**
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements-web.txt
   ```
   Если `activate` ругается на политику выполнения (PowerShell):
   `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
   и повторить активацию.
5. **Запуск:**
   ```cmd
   python webapp.py
   ```
   или просто двойной клик по **`запуск_мастера.bat`** в папке route_app
   (сам возьмёт .venv, если он есть).
6. Открыть в браузере: **http://127.0.0.1:8077**

Каждый следующий запуск: `cd KIMIK3\route_app` → `.venv\Scripts\activate` →
`python webapp.py`.

## 3. macOS

1. **Python и Git** (нужен Homebrew: https://brew.sh):
   ```bash
   brew install python git
   python3 --version
   ```
   Git также ставится вместе с Xcode Command Line Tools: `xcode-select --install`.
2. **Скачать проект:**
   ```bash
   cd ~/Documents
   git clone https://github.com/shulgaop/KIMIK3.git
   cd KIMIK3/route_app
   ```
3. **Виртуальное окружение и зависимости:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-web.txt
   ```
4. **Запуск:**
   ```bash
   python3 webapp.py
   ```
5. Открыть в браузере: **http://127.0.0.1:8077**

## 4. Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
cd ~
git clone https://github.com/shulgaop/KIMIK3.git
cd KIMIK3/route_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-web.txt
python3 webapp.py
```

Открыть в браузере: **http://127.0.0.1:8077**

## 5. Другие Linux (Fedora, Arch)

- Fedora: `sudo dnf install python3 python3-pip git`
- Arch: `sudo pacman -S python python-pip git`

Дальше — как в п. 4, начиная с `git clone`.

## 6. Запуск на сервере (доступ из сети)

```bash
python3 webapp.py --host 0.0.0.0 --port 8077
```
Интерфейс будет доступен по `http://<адрес-сервера>:8077`. Открытый в интернет
без обратного прокси и авторизации не выставляйте — аутентификации в MVP нет.

## 7. Проверка установки

```bash
# из папки route_app, при активированном .venv
python3 scripts/gpx_analyze.py --help
python3 scripts/weather.py --help
python3 webapp.py   # в браузере открывается мастер
```

## 8. Обновление до новой версии

```bash
cd KIMIK3
git pull
cd route_app && pip install -r requirements-web.txt   # если менялись зависимости
```
Ваши проекты (`route_app/projects/`) и настройки обучения (`route_app/learn/`)
при обновлении сохраняются — они не входят в репозиторий.

## 9. Частые проблемы

| Симптом | Решение |
|---|---|
| `python: command not found` / «не является командой» | Python не в PATH — переустановите с галочкой «Add to PATH» (Win) или используйте `python3` (mac/Linux) |
| `pip install` падает по сети | `pip install -r requirements-web.txt -i https://pypi.org/simple` |
| Шаг «Погода» пишет «Open-Meteo недоступен» | Проверьте интернет/файрвол; скрипт сам повторяет запрос 3 раза |
| Порт 8077 занят | `python3 webapp.py --port 8080` |
| Аудиогид не ставится | `pip install edge-tts -i https://pypi.org/simple` |

Дальше — **USER_GUIDE.md** (как пользоваться мастером и обучением).
