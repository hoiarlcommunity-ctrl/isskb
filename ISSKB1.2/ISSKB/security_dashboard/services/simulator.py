"""
Real-time simulation loop (PostgreSQL / asyncpg).

- Перемещает подвижные устройства по патрульным маршрутам
- Движение только если устройство онлайн И в режиме patrol (или alarm/active/warning)
- Офлайн / maintenance / idle устройства стоят на месте
- Broadcasts: position_update [{device_id, latitude, longitude}]
"""
import asyncio
import random
from datetime import datetime, timezone

from database.connection import DSN
from websocket.manager import manager
import asyncpg

# ── Константы движения ────────────────────────────────────────────────────────
TICK_INTERVAL  = 2.0
MOVE_STEP      = 0.10
WAYPOINT_DIST  = 0.0004
JITTER         = 0.00006

# ── Маршруты патрулирования ────────────────────────────────────────────────────
# Район: 56.011318, 37.847164
_PATROL_ROUTES: dict[str, list[tuple[float, float]]] = {
    # ── РАЗВЕДКА — мобильный разведдозор ──
    "RAZV-021": [
        (56.0200, 37.8380),
        (56.0260, 37.8320),
        (56.0310, 37.8400),
        (56.0280, 37.8520),
        (56.0220, 37.8480),
        (56.0180, 37.8400),
    ],
    # ── РЭР — мобильная станция ──
    "RER-004": [
        (56.0220, 37.8530),
        (56.0280, 37.8600),
        (56.0250, 37.8720),
        (56.0180, 37.8700),
        (56.0150, 37.8600),
        (56.0190, 37.8530),
    ],
    # ── БпЛА — мультироторные дроны ──
    "UAV-001": [
        (56.0220, 37.8560),
        (56.0300, 37.8620),
        (56.0320, 37.8500),
        (56.0280, 37.8380),
        (56.0200, 37.8400),
        (56.0180, 37.8500),
    ],
    "UAV-002": [
        (56.0070, 37.8400),
        (55.9980, 37.8350),
        (55.9920, 37.8420),
        (55.9950, 37.8560),
        (56.0020, 37.8520),
        (56.0060, 37.8450),
    ],
    # ── БпЛА — самолётного типа (большой маршрут) ──
    "UAV-011": [
        (56.0320, 37.8580),
        (56.0380, 37.8700),
        (56.0300, 37.8850),
        (56.0150, 37.8900),
        (55.9950, 37.8750),
        (55.9880, 37.8550),
        (55.9920, 37.8350),
        (56.0050, 37.8250),
        (56.0200, 37.8300),
        (56.0300, 37.8420),
    ],
    # ── НРКТ — гусеничные роботы ──
    "NRKT-001": [
        (56.0230, 37.8500),
        (56.0280, 37.8560),
        (56.0310, 37.8480),
        (56.0280, 37.8400),
        (56.0230, 37.8420),
        (56.0210, 37.8470),
    ],
    "NRKT-002": [
        (55.9970, 37.8360),
        (55.9920, 37.8300),
        (55.9880, 37.8380),
        (55.9900, 37.8480),
        (55.9950, 37.8500),
        (55.9980, 37.8430),
    ],
    # ── НРКТ — колёсные роботы ──
    "NRKT-011": [
        (56.0170, 37.8580),
        (56.0120, 37.8680),
        (56.0060, 37.8720),
        (56.0020, 37.8650),
        (56.0060, 37.8560),
        (56.0130, 37.8540),
    ],
    "NRKT-012": [
        (56.0300, 37.8380),
        (56.0340, 37.8440),
        (56.0320, 37.8530),
        (56.0270, 37.8500),
        (56.0250, 37.8420),
        (56.0270, 37.8360),
    ],
}

_patrol_idx: dict[str, int] = {sn: 0 for sn in _PATROL_ROUTES}
_MOVING_MODES = {"patrol", "active", "alarm", "warning"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def simulation_loop():
    print("[SIM] Simulation loop starting…")
    await asyncio.sleep(4)

    while True:
        try:
            conn = await asyncpg.connect(DSN)
            try:
                updates = await _tick(conn)
            finally:
                await conn.close()

            if updates and manager.client_count > 0:
                await manager.broadcast("position_update", updates)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[SIM] Ошибка: {exc}")

        await asyncio.sleep(TICK_INTERVAL)


async def _tick(conn: asyncpg.Connection) -> list[dict]:
    """Один тик симуляции — перемещаем все активные мобильные устройства."""
    rows = await conn.fetch("""
        SELECT
            d.id,
            d.serial_number,
            dp.latitude,
            dp.longitude,
            ds.online_status,
            ds.operational_mode
        FROM devices d
        JOIN device_states    ds ON ds.device_id = d.id
        JOIN device_positions dp ON dp.device_id = d.id AND dp.is_current = TRUE
        WHERE d.is_mobile = TRUE
          AND d.serial_number = ANY($1::text[])
    """, list(_PATROL_ROUTES.keys()))

    if not rows:
        return []

    updates = []

    for r in rows:
        serial = r["serial_number"]
        dev_id = r["id"]
        mode   = r["operational_mode"]
        online = r["online_status"]

        if not online or mode not in _MOVING_MODES:
            continue

        route   = _PATROL_ROUTES[serial]
        idx     = _patrol_idx[serial]
        tgt_lat, tgt_lon = route[idx]
        cur_lat = float(r["latitude"])
        cur_lon = float(r["longitude"])

        dlat = tgt_lat - cur_lat
        dlon = tgt_lon - cur_lon

        if abs(dlat) + abs(dlon) < WAYPOINT_DIST:
            _patrol_idx[serial] = (idx + 1) % len(route)
            idx = _patrol_idx[serial]
            tgt_lat, tgt_lon = route[idx]
            dlat = tgt_lat - cur_lat
            dlon = tgt_lon - cur_lon

        new_lat = round(cur_lat + dlat * MOVE_STEP + random.uniform(-JITTER, JITTER), 7)
        new_lon = round(cur_lon + dlon * MOVE_STEP + random.uniform(-JITTER, JITTER), 7)

        await conn.execute(
            "UPDATE device_positions SET is_current = FALSE WHERE device_id = $1",
            dev_id,
        )
        await conn.execute(
            """INSERT INTO device_positions
                   (device_id, latitude, longitude, speed, is_current, recorded_at)
               VALUES ($1, $2, $3, $4, TRUE, NOW())""",
            dev_id,
            new_lat,
            new_lon,
            round(random.uniform(1.5, 5.5), 1),
        )
        await conn.execute(
            """DELETE FROM device_positions
               WHERE device_id = $1
                 AND id NOT IN (
                     SELECT id FROM device_positions
                     WHERE device_id = $1
                     ORDER BY recorded_at DESC LIMIT 100
                 )""",
            dev_id,
        )

        updates.append({
            "device_id": dev_id,
            "latitude":  new_lat,
            "longitude": new_lon,
        })

    return updates
