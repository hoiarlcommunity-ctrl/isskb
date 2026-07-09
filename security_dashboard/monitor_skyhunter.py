"""
SkyHunter Live Monitor
======================
Запуск: python monitor_skyhunter.py

При подключении:
  1. Проверяет все открытые порты SkyHunter
  2. Показывает версию PostgreSQL, время устройства, статистику
  3. Выводит ВСЕ таблицы со всеми данными (systems, devices, white_list, targets)
  4. Затем слушает altus.targets в реальном времени
  5. Бьёт пульс каждые 15 сек

Нажмите Ctrl+C для выхода.
"""

import asyncio
import json
import socket
import sys
from datetime import datetime
from pathlib import Path

_CFG_FILE = Path(__file__).parent / "config" / "skyhunter.json"
_DEFAULTS = {
    "host": "192.168.1.154",
    "port": 5432,
    "database": "postgres",
    "user": "master",
    "password": "m",
    "poll_interval_s": 1.0,
    "reconnect_interval_s": 5.0,
}

def _load_cfg() -> dict:
    try:
        if _CFG_FILE.exists():
            d = json.loads(_CFG_FILE.read_text(encoding="utf-8"))
            return {**_DEFAULTS, **d}
    except Exception:
        pass
    return dict(_DEFAULTS)

# ── ANSI ──────────────────────────────────────────────────────────────────────
_G = "\033[92m"; _R = "\033[91m"; _Y = "\033[93m"
_C = "\033[96m"; _D = "\033[2m";  _B = "\033[1m"; _W = "\033[0m"
_M = "\033[95m"  # magenta

if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")

def _p(msg: str, color: str = "") -> None:
    print(f"{_D}[{_ts()}]{_W} {color}{msg}{_W}", flush=True)

def _h(title: str) -> None:
    pad = max(0, 52 - len(title))
    print(f"\n{_B}┌─ {title} {'─' * pad}┐{_W}", flush=True)

def _row(key: str, val, color: str = _C) -> None:
    print(f"  {_D}{key:<28}{_W} {color}{val}{_W}", flush=True)

def _sep() -> None:
    print(f"{_D}{'─' * 56}{_W}", flush=True)


# ── 1. Проверка портов (синхронно, до asyncpg) ────────────────────────────────

_PORTS = {
    22:    "SSH",
    80:    "HTTP",
    443:   "HTTPS",
    5432:  "PostgreSQL",
    22001: "SkyHunter-1",
    23400: "SkyHunter WS",
}

def _scan_ports(host: str, timeout: float = 1.0) -> dict[int, bool]:
    results = {}
    for port in _PORTS:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            ok = s.connect_ex((host, port)) == 0
            s.close()
            results[port] = ok
        except Exception:
            results[port] = False
    return results


# ── 2. Исследование PostgreSQL ────────────────────────────────────────────────

async def _pg_info(conn) -> None:
    """Версия, время, uptime, активные соединения."""
    _h("PostgreSQL — состояние сервера")

    # Версия
    try:
        ver = await conn.fetchval("SELECT version()")
        _row("Версия", ver.split(",")[0] if ver else "—")
    except Exception as e:
        _row("Версия", f"ошибка: {e}", _R)

    # Время на устройстве
    try:
        srv_time = await conn.fetchval("SELECT now()")
        local_time = datetime.now()
        diff_sec = abs((srv_time.replace(tzinfo=None) - local_time).total_seconds())
        _row("Время SkyHunter", str(srv_time)[:19])
        _row("Время локальное", str(local_time)[:19])
        color = _G if diff_sec < 5 else _Y
        _row("Разница часов", f"{diff_sec:.1f} сек", color)
    except Exception as e:
        _row("Время", f"ошибка: {e}", _R)

    # Uptime сервера
    try:
        uptime = await conn.fetchval(
            "SELECT now() - pg_postmaster_start_time()"
        )
        _row("PostgreSQL работает", str(uptime).split(".")[0])
    except Exception:
        pass

    # Активные соединения
    try:
        conns = await conn.fetch(
            """SELECT client_addr, state, application_name, query_start
               FROM pg_stat_activity
               WHERE datname IS NOT NULL
               ORDER BY query_start DESC NULLS LAST"""
        )
        _row("Активных соединений", len(conns))
        for c in conns:
            addr  = str(c["client_addr"] or "local")
            state = c["state"] or "—"
            app   = c["application_name"] or "—"
            _row(f"  {addr}", f"[{state}] {app}", _D)
    except Exception as e:
        _row("Соединения", f"ошибка: {e}", _R)

    # Размер БД
    try:
        size = await conn.fetchval(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        )
        _row("Размер базы данных", size)
    except Exception:
        pass


async def _dump_table(conn, schema: str, table: str) -> None:
    """Показывает все строки таблицы."""
    fqt = f'"{schema}"."{table}"'
    _h(f"altus.{table}")

    try:
        # Колонки
        cols = await conn.fetch(
            """SELECT column_name, data_type
               FROM information_schema.columns
               WHERE table_schema=$1 AND table_name=$2
               ORDER BY ordinal_position""",
            schema, table
        )
        col_str = ", ".join(f"{_C}{c['column_name']}{_D}({c['data_type']}){_W}" for c in cols)
        print(f"  Поля: {col_str}", flush=True)

        cnt = await conn.fetchval(f"SELECT COUNT(*) FROM {fqt}")
        _row("Строк всего", cnt, _G if cnt and cnt > 0 else _D)

        if cnt == 0:
            _row("Данные", "(таблица пуста)", _D)
            return

        # Для targets — только последние 5 (может быть много)
        limit = 5 if table == "targets" else 100
        order = "ORDER BY id DESC" if table == "targets" else "ORDER BY id"

        rows = await conn.fetch(f"SELECT * FROM {fqt} {order} LIMIT {limit}")
        label = "Последние записи" if table == "targets" else "Все записи"
        print(f"\n  {_B}{label}:{_W}", flush=True)

        for row in rows:
            d = dict(row)
            line_parts = []
            for k, v in d.items():
                sv = str(v)
                if len(sv) > 50:
                    sv = sv[:47] + "..."
                line_parts.append(f"{_D}{k}{_W}={_C}{sv}{_W}")
            print(f"  → {' | '.join(line_parts)}", flush=True)

    except Exception as e:
        _row("Ошибка", str(e), _R)


async def _discover(conn) -> None:
    """Полное исследование БД SkyHunter."""
    await _pg_info(conn)

    # Список всех таблиц
    _h("Все таблицы в базе")
    tables = await conn.fetch(
        """SELECT table_schema, table_name
           FROM information_schema.tables
           WHERE table_type='BASE TABLE'
             AND table_schema NOT IN ('pg_catalog','information_schema')
           ORDER BY table_schema, table_name"""
    )
    if not tables:
        _row("Таблиц", "не найдено", _R)
    else:
        for t in tables:
            cnt = 0
            fqt = f'"{t["table_schema"]}"."{t["table_name"]}"'
            try:
                cnt = await conn.fetchval(f"SELECT COUNT(*) FROM {fqt}")
            except Exception:
                pass
            status = f"{_G}{cnt} строк{_W}" if cnt else f"{_D}пусто{_W}"
            print(
                f"  {_C}{t['table_schema']}.{t['table_name']:<28}{_W}  {status}",
                flush=True,
            )

    # Детально каждую таблицу altus.*
    altus_tables = [t["table_name"] for t in tables if t["table_schema"] == "altus"]
    priority = ["systems", "devices", "white_list", "targets"]
    ordered  = [x for x in priority if x in altus_tables]
    ordered += [x for x in altus_tables if x not in priority]

    for tname in ordered:
        await _dump_table(conn, "altus", tname)

    print(flush=True)


# ── 3. Основной цикл ──────────────────────────────────────────────────────────

async def _monitor(cfg: dict) -> None:
    try:
        import asyncpg
    except ImportError:
        print(f"{_R}Ошибка: asyncpg не установлен. Запустите: pip install asyncpg{_W}")
        sys.exit(1)

    host   = cfg["host"]
    port   = int(cfg["port"])
    db     = cfg["database"]
    user   = cfg["user"]
    pw     = cfg["password"]
    poll   = float(cfg.get("poll_interval_s", 1.0))
    reconn = float(cfg.get("reconnect_interval_s", 5.0))
    dsn    = f"postgresql://{user}:{pw}@{host}:{port}/{db}"

    print(f"""
{_B}╔══════════════════════════════════════════════════════╗
║         SKYHUNTER  LIVE  MONITOR  v2                 ║
╚══════════════════════════════════════════════════════╝{_W}
  Устройство : {_C}{host}:{port}{_W}
  База данных: {_C}{db}{_W}
  {_D}Ctrl+C — выход{_W}
""", flush=True)

    # ── Сканирование портов (один раз, синхронно) ─────────────────────────────
    _h("Сканирование портов SkyHunter")
    print(f"  {_D}(timeout 1 сек на порт...){_W}", flush=True)
    port_results = _scan_ports(host, timeout=1.0)
    for p, name in _PORTS.items():
        ok = port_results.get(p, False)
        icon  = f"{_G}●  ОТКРЫТ{_W}" if ok else f"{_D}○  закрыт{_W}"
        print(f"  {p:<6} {name:<16} {icon}", flush=True)
    print(flush=True)

    # ── Основной цикл ─────────────────────────────────────────────────────────
    conn = None
    last_id    = 0
    total      = 0
    discovered = False
    hb_tick    = 0
    was_conn   = False

    while True:
        if conn is None:
            _p(f"Подключение к PostgreSQL {host}:{port}...", _D)
            try:
                conn = await asyncpg.connect(dsn, timeout=5)
                row  = await conn.fetchrow(
                    "SELECT COALESCE(MAX(id), 0) AS mx FROM altus.targets"
                )
                last_id    = row["mx"]
                total      = 0
                discovered = False
                hb_tick    = 0
                was_conn   = True
                _p(f"{_G}ПОДКЛЮЧЕНО{_W}  SkyHunter онлайн", _G)
            except Exception as e:
                msg = (
                    f"Соединение потеряно. Повтор через {int(reconn)} сек..." if was_conn
                    else f"Нет ответа от {host}:{port}  (подключи LAN, повтор через {int(reconn)} сек)"
                )
                _p(f"{msg}  {_D}{e}{_W}", _R if was_conn else _Y)
                was_conn = False
                discovered = False
                await asyncio.sleep(reconn)
                continue

        # Разведка при первом подключении
        if not discovered:
            try:
                await _discover(conn)
            except Exception as e:
                _p(f"Ошибка разведки: {e}", _R)
            finally:
                discovered = True
            _sep()
            _p(f"Слушаю altus.targets (каждые {poll} сек)...  {_D}пульс каждые ~15 сек{_W}", _D)

        # Опрос новых целей
        try:
            rows = await conn.fetch(
                """SELECT id, drone_id, latitude_deg, longitude_deg
                   FROM altus.targets WHERE id > $1
                   ORDER BY id ASC LIMIT 50""",
                last_id,
            )
        except Exception as e:
            _p(f"Ошибка чтения: {e}", _R)
            try:
                await conn.close()
            except Exception:
                pass
            conn      = None
            was_conn  = False
            discovered = False
            await asyncio.sleep(reconn)
            continue

        if rows:
            for r in rows:
                lat = f"{float(r['latitude_deg']):.6f}"  if r["latitude_deg"]  is not None else "—"
                lon = f"{float(r['longitude_deg']):.6f}" if r["longitude_deg"] is not None else "—"
                total  += 1
                last_id = r["id"]
                print(
                    f"{_D}[{_ts()}]{_W} {_G}▶ ЦЕЛЬ{_W} "
                    f"#{_B}{r['id']}{_W}  "
                    f"drone_id={_C}{r['drone_id']}{_W}  "
                    f"lat={lat}  lon={lon}",
                    flush=True,
                )
            _p(f"Сессия: {_B}{total}{_W} {_D}целей  last_id={last_id}{_W}", _D)
        else:
            hb_tick += 1
            if hb_tick >= max(1, int(15 / max(poll, 0.5))):
                hb_tick = 0
                # Пульс: текущее время на SkyHunter + счётчик
                try:
                    srv_now = await conn.fetchval("SELECT now()")
                    srv_str = str(srv_now)[:19]
                except Exception:
                    srv_str = "—"
                _p(
                    f"{_G}●{_W} SkyHunter онлайн  "
                    f"время устр-ва={_C}{srv_str}{_W}  "
                    f"{_D}целей нет  сессия={total}  last_id={last_id}{_W}",
                    _D,
                )

        await asyncio.sleep(poll)


async def _main() -> None:
    cfg = _load_cfg()
    try:
        await _monitor(cfg)
    except KeyboardInterrupt:
        print(f"\n{_D}Мониторинг остановлен.{_W}")

if __name__ == "__main__":
    asyncio.run(_main())
