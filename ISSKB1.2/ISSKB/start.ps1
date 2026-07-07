#Requires -Version 5.1
# SENTINEL ISSKB — полный автозапуск
# Запускает Docker, PostgreSQL, проверяет БД, поднимает сервер

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$Host.UI.RawUI.WindowTitle = "SENTINEL ISSKB — Запуск"

$APP_DIR   = Join-Path $PSScriptRoot "security_dashboard"
$CONTAINER = "sentinel-postgres"
$DATABASE  = "sentinel_isskb"
$AUTH_DB   = "sentinel_auth"
$PORT      = 8001
$URL       = "http://localhost:$PORT"

# ── Хелперы вывода ───────────────────────────────────────────────────────────

function Hdr($text) {
    Write-Host "  $text" -ForegroundColor Cyan
}
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
function Divider {
    Write-Host ("  " + ("─" * 52)) -ForegroundColor DarkGray
}

# ── Шапка ────────────────────────────────────────────────────────────────────

Clear-Host
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║    SENTINEL  ·  ISSKB  ·  Запуск системы        ║" -ForegroundColor Cyan
Write-Host "  ║    База: sentinel_isskb   Порт: 8001             ║" -ForegroundColor DarkCyan
Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── ШАГ 1: Docker Desktop ────────────────────────────────────────────────────

Hdr "1/5  Docker Desktop"
Divider

$dockerTest = docker info 2>&1
if ($LASTEXITCODE -eq 0) {
    OK "Docker Desktop уже запущен"
} else {
    INFO "Docker Desktop не запущен — запускаю..."

    $candidates = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Docker\Docker Desktop.exe"
    )
    $dockerExe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $dockerExe) {
        FAIL "Docker Desktop не найден. Установите его с https://www.docker.com/products/docker-desktop/"
    }

    Start-Process $dockerExe
    INFO "Ожидаю инициализацию Docker Desktop (до 90 сек)..."

    $waited = 0
    $ready  = $false
    while ($waited -lt 90) {
        Start-Sleep 5
        $waited += 5
        Write-Host "  [ .. ] ... $waited сек" -ForegroundColor DarkGray
        $t = docker info 2>&1
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    }
    if (-not $ready) {
        FAIL "Docker Desktop не ответил за 90 секунд. Запустите вручную и повторите."
    }
    OK "Docker Desktop запущен ($waited сек)"
}

Write-Host ""

# ── ШАГ 2: Контейнер PostgreSQL ──────────────────────────────────────────────

Hdr "2/5  Контейнер PostgreSQL ($CONTAINER)"
Divider

$state = docker inspect --format "{{.State.Status}}" $CONTAINER 2>&1
if ($LASTEXITCODE -ne 0) {
    INFO "Контейнер не найден — создаю..."
    docker run -d `
        --name $CONTAINER `
        -e POSTGRES_USER=sentinel_user `
        -e POSTGRES_PASSWORD=sentinel123 `
        -e POSTGRES_DB=sentinel `
        -p 5432:5432 `
        -v sentinel-pgdata:/var/lib/postgresql/data `
        --restart unless-stopped `
        postgres:16-alpine | Out-Null

    if ($LASTEXITCODE -ne 0) { FAIL "Не удалось создать контейнер $CONTAINER" }
    OK "Контейнер создан и запущен (первый старт)"
} elseif ($state -eq "running") {
    OK "Контейнер уже запущен"
} else {
    INFO "Контейнер остановлен (статус: $state) — запускаю..."
    docker start $CONTAINER | Out-Null
    if ($LASTEXITCODE -ne 0) { FAIL "Не удалось запустить контейнер $CONTAINER" }
    OK "Контейнер запущен"
}

Write-Host ""

# ── ШАГ 3: Готовность PostgreSQL ─────────────────────────────────────────────

Hdr "3/5  Готовность PostgreSQL"
Divider
INFO "Жду принятия соединений..."

$waited = 0
$pgOK   = $false
while ($waited -lt 40) {
    $pg = docker exec $CONTAINER pg_isready -U sentinel_user 2>&1
    if ($LASTEXITCODE -eq 0) { $pgOK = $true; break }
    Start-Sleep 2
    $waited += 2
    Write-Host "  [ .. ] ... $waited сек" -ForegroundColor DarkGray
}
if (-not $pgOK) {
    FAIL "PostgreSQL не ответил за 40 секунд"
}
OK "PostgreSQL принимает соединения ($waited сек)"
Write-Host ""

# ── ШАГ 4: Базы данных (sentinel_isskb + sentinel_auth) ─────────────────────

Hdr "4/5  Базы данных"
Divider

foreach ($db in @($DATABASE, $AUTH_DB)) {
    $dbTest = docker exec $CONTAINER psql -U sentinel_user -d $db -c "SELECT 1;" 2>&1
    if ($LASTEXITCODE -ne 0) {
        INFO "База $db не найдена — создаю..."
        docker exec $CONTAINER psql -U sentinel_user -d sentinel `
            -c "CREATE DATABASE $db OWNER sentinel_user;" | Out-Null
        if ($LASTEXITCODE -ne 0) { FAIL "Не удалось создать базу $db" }
        OK "База данных $db создана"
    } else {
        OK "База данных $db существует"
    }
}
Write-Host ""

# ── ШАГ 5: Python-зависимости ────────────────────────────────────────────────

Hdr "5/5  Python и зависимости"
Divider

# Определяем РАБОЧИЙ интерпретатор Python.
# ВАЖНО: голый "python" на этом ПК — заглушка Microsoft Store
# (C:\Windows\System32\python), которая молча ничего не запускает и
# возвращает пустой код возврата. Поэтому предпочитаем лаунчер py -3.13
# и принимаем интерпретатор только если он реально печатает "Python 3".
$pyCandidates = @(
    @{ Exe = "py";     Args = @("-3.13") },
    @{ Exe = "py";     Args = @("-3") },
    @{ Exe = "python"; Args = @() }
)
$PyExe = $null; $PyArgs = @()
foreach ($c in $pyCandidates) {
    $exe = $c.Exe; $a = $c.Args
    try {
        $v = & $exe @a --version 2>&1
        if ($LASTEXITCODE -eq 0 -and "$v" -match "Python 3") { $PyExe = $exe; $PyArgs = $a; break }
    } catch { }
}
if (-not $PyExe) { FAIL "Рабочий Python 3 не найден. Установите Python 3.11+ (с лаунчером py) с https://www.python.org/downloads/ и отключите заглушку Microsoft Store (Параметры → Псевдонимы выполнения приложений)." }
$pyVer = (& $PyExe @PyArgs --version 2>&1)
OK "Python: $pyVer  (запуск: $PyExe $($PyArgs -join ' '))"

$depsOK = & $PyExe @PyArgs -c "import fastapi, uvicorn, asyncpg, multipart, psutil, bcrypt, jose, httpx; print('ok')" 2>&1
if ($depsOK -notmatch "ok") {
    INFO "Устанавливаю зависимости ОФЛАЙН из wheels\ (без интернета)..."
    & $PyExe @PyArgs -m pip install --no-index --find-links (Join-Path $APP_DIR "wheels") `
        -r (Join-Path $APP_DIR "requirements.txt") --quiet
    if ($LASTEXITCODE -ne 0) { FAIL "Офлайн-установка не удалась. Проверьте папку security_dashboard\wheels\ (см. РАЗВЁРТЫВАНИЕ_НА_ДРУГОМ_ПК.md, разд. 7.2)" }
    OK "Зависимости установлены (офлайн, без обращения к интернету)"
} else {
    OK "Все зависимости установлены"
}
Write-Host ""

# ── ЗАПУСК СЕРВЕРА ────────────────────────────────────────────────────────────

# Определяем локальный IP этого ПК для доступа из сети (исключаем виртуальные/VPN адаптеры)
$lanIp = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and
        $_.PrefixOrigin -ne 'WellKnown' -and
        $_.InterfaceAlias -notmatch 'vEthernet|WSL|Loopback|Default Switch|tun|tap|VPN'
    } | Select-Object -First 1 -ExpandProperty IPAddress)
if (-not $lanIp) { $lanIp = "IP_ЭТОГО_ПК" }

Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║   Все проверки пройдены. Запускаю сервер...       ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "   Этот ПК:        " -NoNewline -ForegroundColor DarkGray; Write-Host "http://localhost:$PORT" -ForegroundColor White
Write-Host "   Из локальной сети: " -NoNewline -ForegroundColor DarkGray; Write-Host ("http://{0}:{1}" -f $lanIp, $PORT) -ForegroundColor Cyan
Write-Host "   API Docs:       " -NoNewline -ForegroundColor DarkGray; Write-Host "http://localhost:$PORT/api/docs" -ForegroundColor DarkGray
Write-Host ""
Write-Host "   Чтобы другие ПК в сети могли заходить — один раз запустите" -ForegroundColor Yellow
Write-Host "   ОТКРЫТЬ_ДОСТУП_ПО_СЕТИ.bat (от имени администратора)." -ForegroundColor Yellow
Write-Host "   Остановить сервер: Ctrl+C" -ForegroundColor DarkGray
Write-Host ""

Set-Location $APP_DIR
$env:PYTHONUTF8 = "1"
& $PyExe @PyArgs main.py

# Если сервер упал — не закрывать окно
Write-Host ""
Write-Host "  Сервер завершил работу. Нажмите Enter для выхода..." -ForegroundColor Yellow
Read-Host | Out-Null
