@echo off
chcp 65001 >nul 2>&1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ОТКРЫТЬ_ДОСТУП_ПО_СЕТИ.ps1"
