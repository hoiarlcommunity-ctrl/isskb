"""
SkyHunter poller — подключается к PostgreSQL базе устройства SkyHunter
и опрашивает таблицу altus.targets на новые обнаруженные цели.

Pull-based: SkyHunter сам пишет цели в свою PostgreSQL,
мы её читаем. Ничего слать устройству не надо — только подключиться.

Данные пишутся в ext_devices как одна запись "SkyHunter-1":
  - online      = статус соединения
  - status      = "alarm" при активных целях, "idle" когда тихо
  - latitude    = физическое место SkyHunter (из config/skyhunter.json)
  - longitude   = то же
  - extra_data  = {last_drone_id, last_detection_lat/lon, last_detection_at,
                   detections_session}

Конфиг: security_dashboard/config/skyhunter.json
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

import services.syslog as syslog

_CONFIG_FILE = Path(__file__).parent.parent / "config" / "skyhunter.json"

_DEFAULTS: dict = {
    "enabled": True,
    "host": "192.168.1.154",
    "port": 5432,
    "database": "postgres",
    "user": "master",
    "password": "m",
    "device_name": "SkyHunter-1",
    "device_lat": None,
    "device_lon": None,
    "poll_interval_s": 1.0,
    "reconnect_interval_s": 10.0,
    "idle_timeout_s": 30,
}


def _load_config() -> dict:
    try:
        if _CONFIG_FILE.exists():
            data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            return {**_DEFAULTS, **data}
    except Exception as e:
        _log(f"Ошибка чтения config/skyhunter.json: {e}", "WARN")
    return dict(_DEFAULTS)


def _log(msg: str, level: str = "INFO") -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[SKYHUNTER {level}] {ts} {msg}", flush=True)


async def skyhunter_loop() -> None:
    cfg = _load_config()

    if not cfg.get("enabled"):
        _log("Поллер отключён (enabled=false в config/skyhunter.json)", "INFO")
        syslog.add("info", "skyhunter", "SkyHunter поллер отключён")
        return

    sh_dsn = (
        f"postgresql://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['database']}"
    )
    device_name        = cfg["device_name"]
    device_lat         = cfg.get("device_lat")
    device_lon         = cfg.get("device_lon")
    poll_interval      = float(cfg.get("poll_interval_s", 1.0))
    reconnect_interval = float(cfg.get("reconnect_interval_s", 10.0))
    idle_timeout       = float(cfg.get("idle_timeout_s", 30))

    _log(f"Запуск. Подключаюсь к {cfg['host']}:{cfg['port']} / {cfg['database']}")
    syslog.add("info", "skyhunter", f"SkyHunter поллер запущен → {cfg['host']}:{cfg['port']}")

    sh_conn: asyncpg.Connection | None = None
    last_id = 0
    last_detection_ts: float = 0.0
    session_count = 0
    was_connected = False

    while True:
        # ── Подключение к SkyHunter PostgreSQL ───────────────────────────────
        if sh_conn is None:
            try:
                sh_conn = await asyncpg.connect(sh_dsn, timeout=5)
                row = await sh_conn.fetchrow(
                    "SELECT COALESCE(MAX(id), 0) AS max_id FROM altus.targets"
                )
                last_id = row["max_id"]
                session_count = 0
                was_connected = True
                _log(f"ПОДКЛЮЧЕНО  last_id={last_id}  ждём новых целей...")
                syslog.add("info", "skyhunter", f"Подключено к SkyHunter, last_id={last_id}")
                await _write_ext_device(
                    device_name, True, "idle",
                    device_lat, device_lon,
                    {"source": "skyhunter", "detections_session": 0},
                )
            except Exception as e:
                if was_connected:
                    _log(f"Соединение потеряно: {e}", "WARN")
                    syslog.add("warn", "skyhunter", f"Соединение с SkyHunter потеряно: {e}")
                    was_connected = False
                else:
                    _log(f"Нет связи с {cfg['host']}:{cfg['port']} — жду {int(reconnect_interval)} сек  ({e})", "WARN")
                    syslog.add("warn", "skyhunter", f"Нет связи с SkyHunter: {e}")

                await _write_ext_device(
                    device_name, False, "idle",
                    device_lat, device_lon,
                    {"source": "skyhunter", "error": str(e)[:120]},
                )
                await asyncio.sleep(reconnect_interval)
                continue

        # ── Опрос новых целей ────────────────────────────────────────────────
        try:
            rows = await sh_conn.fetch(
                """SELECT id, drone_id, latitude_deg, longitude_deg
                   FROM altus.targets
                   WHERE id > $1
                   ORDER BY id ASC
                   LIMIT 50""",
                last_id,
            )
        except Exception as e:
            _log(f"Ошибка опроса: {e}", "ERROR")
            syslog.add("warn", "skyhunter", f"Ошибка опроса altus.targets: {e}")
            try:
                await sh_conn.close()
            except Exception:
                pass
            sh_conn = None
            was_connected = False
            await _write_ext_device(
                device_name, False, "idle",
                device_lat, device_lon,
                {"source": "skyhunter", "error": str(e)[:120]},
            )
            await asyncio.sleep(reconnect_interval)
            continue

        now_ts = datetime.now(timezone.utc)

        if rows:
            last_row = rows[-1]
            last_id  = last_row["id"]
            session_count += len(rows)
            last_detection_ts = asyncio.get_event_loop().time()

            lat_v = float(last_row["latitude_deg"])  if last_row["latitude_deg"]  is not None else None
            lon_v = float(last_row["longitude_deg"]) if last_row["longitude_deg"] is not None else None

            for r in rows:
                r_lat = float(r["latitude_deg"])  if r["latitude_deg"]  is not None else "—"
                r_lon = float(r["longitude_deg"]) if r["longitude_deg"] is not None else "—"
                _log(
                    f"ЦЕЛЬ #{r['id']}  drone_id={r['drone_id']}  "
                    f"lat={r_lat}  lon={r_lon}"
                )

            extra = {
                "source": "skyhunter",
                "last_drone_id": last_row["drone_id"],
                "last_detection_lat": lat_v,
                "last_detection_lon": lon_v,
                "last_detection_at": now_ts.isoformat(),
                "detections_session": session_count,
            }
            syslog.add(
                "info", "skyhunter",
                f"Обнаружено {len(rows)} целей, drone_id={last_row['drone_id']}",
            )
            await _write_ext_device(device_name, True, "alarm", device_lat, device_lon, extra)

        else:
            elapsed = asyncio.get_event_loop().time() - last_detection_ts
            if last_detection_ts > 0 and elapsed > idle_timeout:
                await _write_ext_device(
                    device_name, True, "idle",
                    device_lat, device_lon,
                    {"source": "skyhunter", "detections_session": session_count},
                )

        await asyncio.sleep(poll_interval)


async def _write_ext_device(
    name: str,
    online: bool,
    status: str,
    lat: float | None,
    lon: float | None,
    extra: dict,
) -> None:
    from database.connection import get_pool

    pool = get_pool()
    if pool is None:
        return

    extra_json = json.dumps(extra, ensure_ascii=False, default=str)
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO ext_devices
                       (name, online, status, latitude, longitude, extra_data, received_at, synced_at)
                   VALUES ($1, $2, $3, $4, $5, $6::jsonb, now(), now())
                   ON CONFLICT (name) DO UPDATE SET
                       online      = EXCLUDED.online,
                       status      = EXCLUDED.status,
                       latitude    = COALESCE($4, ext_devices.latitude),
                       longitude   = COALESCE($5, ext_devices.longitude),
                       extra_data  = EXCLUDED.extra_data,
                       received_at = EXCLUDED.received_at,
                       synced_at   = EXCLUDED.synced_at""",
                name, online, status, lat, lon, extra_json,
            )
    except Exception as e:
        syslog.add("error", "skyhunter", f"Ошибка записи в ext_devices: {e}")
        _log(f"Ошибка записи в ext_devices: {e}", "ERROR")
