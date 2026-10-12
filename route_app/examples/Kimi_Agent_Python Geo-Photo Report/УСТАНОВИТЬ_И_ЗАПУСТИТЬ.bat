@echo off
chcp 65001 >nul
title Отчёт о походе - установка и запуск
cd /d "%~dp0"

echo ============================================================
echo   ОТЧЁТ О ПОХОДЕ: проверка и установка всего необходимого
echo ============================================================
echo.
echo Папка: %CD%
echo.

REM ---------- Проверяем, что скрипт на месте ----------
if not exist "hike_report.py" (
    echo ОШИБКА: файл hike_report.py не найден.
    echo Положите этот установщик в ту же папку, где лежит hike_report.py
    echo и ваши фото/видео, и запустите снова.
    echo.
    pause
    exit /b 1
)

REM ---------- 1. Python ----------
echo [1/3] Проверяю Python...

set "PY="
python -c "pass" >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
    goto :python_ok
)
py -c "pass" >nul 2>nul
if not errorlevel 1 (
    set "PY=py"
    goto :python_ok
)

echo Python не найден. Устанавливаю автоматически...
echo.

REM Способ 1: через winget (встроен в Windows 10/11)
winget --version >nul 2>nul
if not errorlevel 1 (
    echo Установка через winget...
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
) else (
    REM Способ 2: скачать установщик с python.org
    echo winget не найден, скачиваю установщик с python.org...
    curl -L -o "%TEMP%\python_installer.exe" "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
    if not exist "%TEMP%\python_installer.exe" goto :python_fail
    echo Запускаю установщик Python ^(тихая установка^)...
    start /wait "" "%TEMP%\python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
)

REM PATH в этом окне не обновился - ищем python.exe напрямую
python -c "pass" >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
    goto :python_ok
)
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" set "PY=%%D\python.exe"
)
if exist "C:\Program Files\Python312\python.exe" set "PY=C:\Program Files\Python312\python.exe"
if defined PY goto :python_ok

:python_fail
echo.
echo ОШИБКА: автоматически установить Python не получилось.
echo Установите его вручную с https://www.python.org/downloads/
echo ^(обязательно поставьте галочку "Add python.exe to PATH"!^)
echo и запустите этот файл снова.
echo.
pause
exit /b 1

:python_ok
echo Python найден:
"%PY%" --version
echo.

REM ---------- 2. Библиотеки ----------
echo [2/3] Проверяю и доустанавливаю библиотеки...
echo ^(уже установленные пропускаются, недостающие скачаются^)
echo.
"%PY%" -m pip install --quiet --upgrade pillow folium openpyxl reverse-geocoder pyosmogps imageio-ffmpeg
if errorlevel 1 (
    echo Что-то пошло не так, пробую ещё раз с подробным выводом...
    "%PY%" -m pip install pillow folium openpyxl reverse-geocoder pyosmogps imageio-ffmpeg
)
"%PY%" -c "import PIL, folium, openpyxl" >nul 2>nul
if errorlevel 1 (
    echo.
    echo ОШИБКА: библиотеки не установились. Проверьте интернет
    echo и запустите этот файл снова.
    echo.
    pause
    exit /b 1
)
echo Библиотеки в порядке.
echo.

REM ---------- 3. Запуск скрипта ----------
echo [3/3] Запускаю обработку фото и видео...
echo ============================================================
echo.
"%PY%" hike_report.py

if errorlevel 1 (
    echo.
    echo ============================================================
    echo Скрипт завершился с ошибкой. Сфотографируйте текст выше
    echo и отправьте мне - разберёмся.
)
echo.
pause
