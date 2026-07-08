#Requires -Version 5.1
# ISSKB setup for Python 3.14.
# Run from ISSKB1.2\ISSKB\security_dashboard:
#   powershell -ExecutionPolicy Bypass -File .\setup_py314.ps1

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
Set-Location -Path $PSScriptRoot

Write-Host "[ISSKB] Python 3.14 setup" -ForegroundColor Cyan

# This project has old local wheels for cp312; Python 3.14 must use fresh PyPI wheels.
if (-not (Test-Path ".\requirements-py314.txt")) {
    throw "requirements-py314.txt not found"
}

# Clear broken SOCKS proxy variables for this PowerShell session.
$proxyVars = @(
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    "PIP_PROXY", "pip_proxy"
)
foreach ($v in $proxyVars) {
    Remove-Item "Env:$v" -ErrorAction SilentlyContinue
}
# Ask Python requests/pip to bypass proxies for all hosts if something outside env leaks in.
$env:NO_PROXY = "*"
$env:no_proxy = "*"
$env:PYTHONUTF8 = "1"

# Force Python Launcher to use 3.14, not 3.11/3.12.
& py -3.14 --version
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.14 not found in py launcher. Check: py -0p"
}

if (Test-Path ".\.venv314") {
    Write-Host "[ISSKB] Removing old .venv314" -ForegroundColor Yellow
    Remove-Item -Recurse -Force ".\.venv314"
}

Write-Host "[ISSKB] Creating .venv314" -ForegroundColor Cyan
& py -3.14 -m venv .venv314
if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }

$py = Join-Path $PSScriptRoot ".venv314\Scripts\python.exe"
& $py --version

Write-Host "[ISSKB] Installing Python 3.14 dependencies from PyPI" -ForegroundColor Cyan
Write-Host "[ISSKB] Note: old .\wheels folder is cp312-only and is intentionally not used." -ForegroundColor DarkGray

# First try: explicitly override any pip proxy setting with empty proxy.
& $py -m pip install --disable-pip-version-check --no-cache-dir --proxy "" -r .\requirements-py314.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "" 
    Write-Host "[ISSKB] First pip attempt failed. Retrying without --proxy override..." -ForegroundColor Yellow
    & $py -m pip install --disable-pip-version-check --no-cache-dir -r .\requirements-py314.txt
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "" 
    Write-Host "[ERROR] Dependencies were not installed." -ForegroundColor Red
    Write-Host "Most likely your system/pip still forces a SOCKS proxy without PySocks support." -ForegroundColor Yellow
    Write-Host "Run these diagnostics and send the output:" -ForegroundColor Yellow
    Write-Host "  Get-ChildItem Env:*proxy*" -ForegroundColor Gray
    Write-Host "  py -3.14 -m pip config debug" -ForegroundColor Gray
    exit 1
}

Write-Host "[ISSKB] Checking imports" -ForegroundColor Cyan
& $py .\check_py314.py
if ($LASTEXITCODE -ne 0) { throw "Import check failed" }

Write-Host "" 
Write-Host "[OK] Python 3.14 environment is ready." -ForegroundColor Green
Write-Host "Run: .\run_py314.bat" -ForegroundColor Green
