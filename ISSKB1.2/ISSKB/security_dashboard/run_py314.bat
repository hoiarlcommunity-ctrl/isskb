@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
set PYTHONUTF8=1

if not exist ".venv314\Scripts\python.exe" (
    echo [ERROR] .venv314 not found.
    echo Run first:
    echo powershell -ExecutionPolicy Bypass -File .\setup_py314.ps1
    pause
    exit /b 1
)

echo [ISSKB] Starting with Python 3.14 venv
".venv314\Scripts\python.exe" main.py
pause
