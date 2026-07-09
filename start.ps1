#Requires -Version 5.1
# SENTINEL ISSKB — полный автозапуск
# Запускает портативный PostgreSQL, проверяет Python, поднимает сервер

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$Host.UI.RawUI.WindowTitle = "SENTINEL ISSKB — Запуск"

$APP_DIR  = Join-Path $PSScriptRoot "security_dashboard"
$PORT     = 8001
$PG_PORT  = 5440
$PG_CTL   = Join-Path $APP_DIR "pgsql\bin\pg_ctl.exe"
$PG_SETUP = Join-Path $APP_DIR "setup_postgres.ps1"

function Hdr($text) { Write-Host "  $text" -ForegroundColor Cyan }
function OK($text) {
    Write-Host "  [" -NoNewline -ForegroundColor DarkGray
    Write-Host " OK " -NoNewline -ForegroundColor Green
    Write-Host "] " -NoNewline -ForegroundColor DarkGray
    Write-Host $text
}
function INFO($text) {
    Write-Host "  [" -NoNewline -ForegroundColor DarkGray
    Write-Host " .. " -NoNewline -ForegroundColor Yellow
    Write-Host "] " -NoNewline -ForegroundColor DarkGray
    Write-Host $text -ForegroundColor Yellow
}
function FAIL($text) {
    Write-Host ""
    Write-Host "  [" -NoNewline -ForegroundColor DarkGray
    Write-Host "FAIL" -NoNewline -ForegroundColor Red
    Write-Host "] $text" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Нажмите Enter для выхода..." -ForegroundColor DarkGray
    Read-Host | Out-Null
    exit 1
}
function Divider { Write-Host ("  " + ("─" * 52)) -ForegroundColor DarkGray }

function Get-WorkingPython {
    $candidates = @()
    $venv314 = Join-Path $APP_DIR ".venv314\Scripts\python.exe"
    if (Test-Path $venv314) { $candidates += @{ Exe = $venv314; Args = @() } }
    $candidates += @(
        @{ Exe = "py";     Args = @("-3.12") },
        @{ Exe = "py";     Args = @("-3.13") },
        @{ Exe = "py";     Args = @("-3.11") },
        @{ Exe = "py";     Args = @("-3") },
        @{ Exe = "python"; Args = @() }
    )
    foreach ($c in $candidates) {
        $exe = $c.Exe; $candArgs = $c.Args
        try {
            $v = & $exe @candArgs --version 2>&1
            if ($LASTEXITCODE -eq 0 -and "$v" -match "Python 3") {
                return @{ Exe = $exe; Args = $candArgs; Version = "$v" }
            }
        } catch { }
    }
    return $null
}

Clear-Host
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║    SENTINEL  ·  ISSKB  ·  Запуск системы        ║" -ForegroundColor Cyan
Write-Host "  ║    База: sentinel_isskb   Порт: 8001             ║" -ForegroundColor DarkCyan
Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── ШАГ 1: портативный PostgreSQL ────────────────────────────────────────────

Hdr "1/3  PostgreSQL (портативный)"
Divider

if (Test-Path $PG_CTL) {
    OK "PostgreSQL найден: $PG_CTL"
} else {
    INFO "PostgreSQL не найден в security_dashboard\pgsql — запускаю установку..."
    if (-not (Test-Path $PG_SETUP)) {
        FAIL "Не найден $PG_SETUP"
    }
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File $PG_SETUP
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $PG_CTL)) {
        FAIL "Не удалось установить портативный PostgreSQL. Запустите security_dashboard\setup_postgres.ps1 вручную и проверьте доступ к интернету."
    }
    OK "PostgreSQL установлен"
}
Write-Host ""

# ── ШАГ 2: Python-зависимости ────────────────────────────────────────────────

Hdr "2/3  Python и зависимости"
Divider

$py = Get-WorkingPython
if (-not $py) {
    FAIL "Рабочий Python 3 не найден. Установите Python 3.12+ с https://www.python.org/downloads/ и включите Python Launcher."
}
$PyExe = $py.Exe
$PyArgs = $py.Args
OK "Python: $($py.Version)  (запуск: $PyExe $($PyArgs -join ' '))"

$pyMajorMinor = (& $PyExe @PyArgs -c "import sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))" 2>&1).ToString().Trim()
$depsCheck = & $PyExe @PyArgs -c "import fastapi, uvicorn, asyncpg, multipart, psutil, bcrypt, jose, httpx; print('ok')" 2>&1
if ($LASTEXITCODE -ne 0 -or "$depsCheck" -notmatch "ok") {
    if ($pyMajorMinor -eq "3.12" -and (Test-Path (Join-Path $APP_DIR "wheels"))) {
        INFO "Устанавливаю зависимости ОФЛАЙН из wheels\ (Python 3.12)..."
        & $PyExe @PyArgs -m pip install --no-index --find-links (Join-Path $APP_DIR "wheels") `
            -r (Join-Path $APP_DIR "requirements.txt") --quiet
    } else {
        INFO "Для этой версии Python нужны свежие колёса — устанавливаю зависимости через pip..."
        & $PyExe @PyArgs -m pip install --disable-pip-version-check --no-cache-dir `
            -r (Join-Path $APP_DIR "requirements-py314.txt")
    }
    if ($LASTEXITCODE -ne 0) {
        FAIL "Установка зависимостей не удалась. Для полностью офлайн-запуска используйте Python 3.12 с папкой security_dashboard\wheels\."
    }
    $depsCheck = & $PyExe @PyArgs -c "import fastapi, uvicorn, asyncpg, multipart, psutil, bcrypt, jose, httpx; print('ok')" 2>&1
    if ($LASTEXITCODE -ne 0 -or "$depsCheck" -notmatch "ok") {
        FAIL "Зависимости установлены не полностью: $depsCheck"
    }
    OK "Зависимости установлены"
} else {
    OK "Все зависимости установлены"
}
Write-Host ""

# ── ШАГ 3: запуск сервера ────────────────────────────────────────────────────

$lanIp = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and
        $_.PrefixOrigin -ne 'WellKnown' -and
        $_.InterfaceAlias -notmatch 'vEthernet|WSL|Loopback|Default Switch|tun|tap|VPN'
    } | Select-Object -First 1 -ExpandProperty IPAddress)
if (-not $lanIp) { $lanIp = "IP_ЭТОГО_ПК" }

Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║   Все проверки пройдены. Запускаю сервер...     ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "   Этот ПК:          " -NoNewline -ForegroundColor DarkGray; Write-Host "http://localhost:$PORT" -ForegroundColor White
Write-Host "   Из локальной сети:" -NoNewline -ForegroundColor DarkGray; Write-Host (" http://{0}:{1}" -f $lanIp, $PORT) -ForegroundColor Cyan
Write-Host "   API Docs:         " -NoNewline -ForegroundColor DarkGray; Write-Host "http://localhost:$PORT/api/docs" -ForegroundColor DarkGray
Write-Host ""
Write-Host "   Чтобы другие ПК в сети могли заходить — один раз запустите" -ForegroundColor Yellow
Write-Host "   ОТКРЫТЬ_ДОСТУП_ПО_СЕТИ.ps1 от имени администратора." -ForegroundColor Yellow
Write-Host "   Остановить сервер: Ctrl+C" -ForegroundColor DarkGray
Write-Host ""

Set-Location $APP_DIR
$env:PYTHONUTF8 = "1"
$env:SENTINEL_PG_EMBEDDED = "1"
$env:SENTINEL_PG_PORT = "$PG_PORT"
$env:SENTINEL_DSN = "postgresql://sentinel_user@127.0.0.1:$PG_PORT/sentinel_isskb"
$env:AUTH_DSN = "postgresql://sentinel_user@127.0.0.1:$PG_PORT/sentinel_auth"
& $PyExe @PyArgs main.py

Write-Host ""
Write-Host "  Сервер завершил работу. Нажмите Enter для выхода..." -ForegroundColor Yellow
Read-Host | Out-Null
