@echo off
chcp 65001 >nul 2>&1
title SENTINEL Command Center
echo.
echo  ==========================================
echo   SENTINEL - Enterprise Security Dashboard
echo  ==========================================
echo.

cd /d "%~dp0"

:: Определяем РАБОЧИЙ Python. Голый "python" на этом ПК — заглушка Microsoft
:: Store (C:\Windows\System32\python): молча ничего не запускает. Предпочитаем
:: лаунчер py -3.13, откатываемся на py -3, затем на python.
set "PYEXE="
py -3.13 --version >nul 2>&1 && set "PYEXE=py -3.13"
if not defined PYEXE ( py -3 --version >nul 2>&1 && set "PYEXE=py -3" )
if not defined PYEXE ( python --version >nul 2>&1 && set "PYEXE=python" )
if not defined PYEXE (
    echo [ERROR] Python 3 not found. Install Python 3.11+ from https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "delims=" %%v in ('%PYEXE% --version 2^>^&1') do echo [*] Using %%v ^(%PYEXE%^)

:: Проверяем зависимости; если чего-то нет — ставим офлайн из wheels\ (без интернета)
%PYEXE% -c "import fastapi, uvicorn, asyncpg, multipart, psutil, bcrypt, jose, httpx" >nul 2>&1
if errorlevel 1 (
    echo [*] Installing dependencies offline from wheels\ ...
    %PYEXE% -m pip install --no-index --find-links wheels -r requirements.txt --quiet
)

echo.
echo [*] Starting server at http://localhost:8001
echo [*] Press Ctrl+C to stop
echo.

set PYTHONUTF8=1
%PYEXE% main.py
pause
