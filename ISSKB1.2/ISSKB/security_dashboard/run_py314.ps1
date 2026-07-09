#Requires -Version 5.1
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
Set-Location -Path $PSScriptRoot
$env:PYTHONUTF8 = "1"

$Py = Join-Path $PSScriptRoot ".venv314\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "[ERROR] .venv314 не найден." -ForegroundColor Red
    Write-Host "Сначала выполните: powershell -ExecutionPolicy Bypass -File .\setup_py314.ps1" -ForegroundColor Yellow
    Read-Host "Нажмите Enter для выхода" | Out-Null
    exit 1
}

Write-Host "[ISSKB] Запуск через Python 3.14 venv" -ForegroundColor Cyan
& $Py main.py
Read-Host "Нажмите Enter для выхода" | Out-Null
