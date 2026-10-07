@echo off
rem Запуск мастера генерации маршрутов (двойной клик в Windows)
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe webapp.py
) else (
  python webapp.py
)
pause
