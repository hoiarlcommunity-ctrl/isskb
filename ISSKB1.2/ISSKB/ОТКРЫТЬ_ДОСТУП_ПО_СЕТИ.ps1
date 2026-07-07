#Requires -Version 5.1
# ─────────────────────────────────────────────────────────────────────────────
#  Открывает порт 8001 в брандмауэре Windows, чтобы другие ПК в локальной сети
#  могли заходить на дашборд SENTINEL ISSKB.
#  Запускать ОДИН РАЗ. Скрипт сам запросит права администратора (UAC).
# ─────────────────────────────────────────────────────────────────────────────

$PORT = 8001
$RULE = "SENTINEL ISSKB (TCP $PORT)"

# ── Самоповышение прав ───────────────────────────────────────────────────────
$id        = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -Verb RunAs -ArgumentList `
        "-NoProfile","-ExecutionPolicy","Bypass","-File","`"$PSCommandPath`""
    exit
}

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

Write-Host ""
Write-Host "  Настройка доступа к SENTINEL ISSKB по локальной сети" -ForegroundColor Cyan
Write-Host "  ────────────────────────────────────────────────────" -ForegroundColor DarkGray

# ── Правило брандмауэра (пересоздаём начисто) ────────────────────────────────
Get-NetFirewallRule -DisplayName $RULE -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $RULE -Direction Inbound -Action Allow `
    -Protocol TCP -LocalPort $PORT -Profile Private,Domain | Out-Null
Write-Host "  [OK] Порт $PORT/TCP разрешён (профили: Частная, Доменная)." -ForegroundColor Green

# ── Проверяем профиль активной сети ──────────────────────────────────────────
$publicNets = Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -eq 'Public' }
if ($publicNets) {
    Write-Host ""
    Write-Host "  [!] ВНИМАНИЕ: активная сеть имеет профиль 'Общедоступная' (Public)." -ForegroundColor Yellow
    Write-Host "      Правило создано только для 'Частная/Доменная' — из такой сети доступа НЕ будет." -ForegroundColor Yellow
    foreach ($n in $publicNets) {
        Write-Host ("      Сеть: {0} (интерфейс {1})" -f $n.Name, $n.InterfaceAlias) -ForegroundColor DarkYellow
    }
    Write-Host "      Смените профиль на 'Частная': Параметры → Сеть → выбрать сеть → Частная." -ForegroundColor Yellow
    Write-Host "      Или из PowerShell (админ):" -ForegroundColor Yellow
    Write-Host "        Set-NetConnectionProfile -InterfaceAlias '<имя>' -NetworkCategory Private" -ForegroundColor Gray
}

# ── Показываем адрес для подключения ─────────────────────────────────────────
$lanIp = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and
        $_.PrefixOrigin -ne 'WellKnown' -and
        $_.InterfaceAlias -notmatch 'vEthernet|WSL|Loopback|Default Switch|tun|tap|VPN'
    } | Select-Object -First 1 -ExpandProperty IPAddress)
if (-not $lanIp) { $lanIp = "<узнайте_через_ipconfig>" }

Write-Host ""
Write-Host "  Готово. Другие ПК в этой же сети заходят по адресу:" -ForegroundColor Green
Write-Host ("      http://{0}:{1}" -f $lanIp, $PORT) -ForegroundColor Cyan
Write-Host ""
Write-Host "  Убедитесь, что сервер запущен (ЗАПУСТИТЬ.bat)." -ForegroundColor DarkGray
Write-Host "  Нажмите Enter для выхода..." -ForegroundColor DarkGray
Read-Host | Out-Null
