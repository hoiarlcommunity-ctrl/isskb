@echo off
chcp 65001 >nul 2>&1
powershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_vm.ps1"
