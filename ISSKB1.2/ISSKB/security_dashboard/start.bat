@echo off
chcp 65001 > nul
echo ===============================================
echo   SENTINEL -- ISSKB (тестовая версия)
echo   БД:     sentinel_isskb
echo   Сервер: http://localhost:8001
echo ===============================================
echo.

cd /d "%~dp0"

:: PostgreSQL встроенный (портативный) — поднимается самим приложением из папки
:: pgsql\. Если её нет — один раз выполните setup_postgres.ps1 (скачает бинарники).
if not exist "pgsql\bin\pg_ctl.exe" (
    echo [!] Портативный PostgreSQL не найден в pgsql\
    echo [!] Запустите один раз: powershell -ExecutionPolicy Bypass -File setup_postgres.ps1
    echo.
)

:: Определяем РАБОЧИЙ Python. Голый "python" на этом ПК — заглушка Microsoft
:: Store (C:\Windows\System32\python): молча ничего не запускает. Предпочитаем
:: лаунчер py -3.13, откатываемся на py -3, затем на python.
set "PYEXE="
py -3.13 --version >nul 2>&1 && set "PYEXE=py -3.13"
if not defined PYEXE ( py -3 --version >nul 2>&1 && set "PYEXE=py -3" )
if not defined PYEXE ( python --version >nul 2>&1 && set "PYEXE=python" )
if not defined PYEXE (
    echo [ERROR] Python 3 не найден. Установите Python 3.11+ с https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [..] PostgreSQL поднимется автоматически при старте
echo [..] Запуск сервера на порту 8001...
echo.

set PYTHONUTF8=1
%PYEXE% main.py
pause
