"""
Synchronisation: ext_devices → main DB tables (devices / device_states / device_positions).

Matching key: device name (case-insensitive).
  • Found   → update device_states + device_positions
  • Missing → create new device (category ext_device) + states + positions

Field mapping:
  field_map = {"system_key": "api_key_in_json"}
  e.g. {"name": "device_name", "online": "is_online", "battery_level": "bat_pct"}

Known system fields (direct DB columns):
  Fixed:    name, online, status, lat/latitude, lon/longitude
  State:    battery_level, signal_strength, error_code
  Position: altitude, heading, speed
  Other:    stored in device_states.extra_state JSONB
"""
import json
from datetime import datetime, timezone
from typing import Any

import asyncpg

# ── Field classification ──────────────────────────────────────────────────────

_FIXED_FIELDS        = {"name", "online", "status", "lat", "lon", "latitude", "longitude"}
_KNOWN_STATE_FIELDS  = {"battery_level", "signal_strength", "error_code"}
_KNOWN_POS_FIELDS    = {"altitude", "heading", "speed"}
# Fields that map to devices table columns (not state/position)
_KNOWN_DEVICE_FIELDS = {
    "external_key", "ip_address", "port", "priority", "device_type",
    "description", "icon_path",
}
_ALL_KNOWN = _FIXED_FIELDS | _KNOWN_STATE_FIELDS | _KNOWN_POS_FIELDS | _KNOWN_DEVICE_FIELDS

# ── Status/value mappers ──────────────────────────────────────────────────────

_ONLINE_MAP: dict[str, bool] = {
    "online": True,  "true": True,  "1": True,  "yes": True,
    "да": True,      "онлайн": True, "on": True, "включено": True,
    "offline": False, "false": False, "0": False, "no": False,
    "нет": False,    "оффлайн": False, "off": False, "выключено": False,
}

_MODE_MAP: dict[str, str] = {
    "active": "active", "working": "active", "работает": "active",
    "on": "active",     "run": "active",     "running": "active", "включено": "active",
    "in_operation": "active", "operational": "active",
    "idle": "idle",     "off": "idle",       "выключено": "idle",
    "inactive": "idle", "standby": "idle",   "stopped": "idle",
    "alarm": "alarm",   "тревога": "alarm",  "alert": "alarm",
    "maintenance": "maintenance", "то": "maintenance", "service": "maintenance",
    "in_maintenance": "maintenance", "in_service": "maintenance",
    "patrol": "patrol", "патруль": "patrol",
    "warning": "warning", "предупреждение": "warning",
}


def _map_online(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    return _ONLINE_MAP.get(str(val).lower().strip(), False)


def _map_mode(val: Any) -> str:
    return _MODE_MAP.get(str(val).lower().strip(), "idle")


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _to_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


# ── Field remapping ───────────────────────────────────────────────────────────

def _remap(raw: dict, field_map: dict) -> dict:
    """
    Apply field_map (system_key → api_key) to a raw record from the external API.
    Result keys are system field names; values are taken from API field names.
    """
    inv = {api_k: sys_k for sys_k, api_k in field_map.items()}
    result = {}
    for api_k, v in raw.items():
        sys_k = inv.get(api_k, api_k)
        result[sys_k] = v
    return result


# ── Category bootstrap ────────────────────────────────────────────────────────

_ext_cat_id: int | None = None


async def _ensure_ext_category(conn: asyncpg.Connection) -> int:
    global _ext_cat_id
    if _ext_cat_id is not None:
        return _ext_cat_id
    row = await conn.fetchrow(
        """INSERT INTO device_categories (code, name, icon, color, tab_id)
           VALUES ('ext_device', 'Внешнее устройство', '🔗', '#64748b', 5)
           ON CONFLICT (code) DO UPDATE SET code = EXCLUDED.code
           RETURNING id"""
    )
    _ext_cat_id = row["id"]
    return _ext_cat_id


# ── Main sync ─────────────────────────────────────────────────────────────────

async def sync_to_main(
    conn: asyncpg.Connection,
    records: list[dict],
    field_map: dict | None = None,
) -> dict:
    """
    Apply field_map remapping, upsert into ext_devices, then mirror each record
    into the main DB (devices / device_states / device_positions).

    Returns: {received, updated, created, skipped}.
    """
    now = datetime.now(timezone.utc)
    created = updated = skipped = 0

    for raw_rec in records:
        # Apply field_map if provided
        rec = _remap(raw_rec, field_map) if field_map else raw_rec

        name: str = str(rec.get("name", "")).strip()
        if not name:
            skipped += 1
            continue

        # Core fields
        online     = _map_online(rec.get("online", False))
        mode       = _map_mode(rec.get("status", "idle"))
        lat        = _to_float(rec.get("lat") or rec.get("latitude"))
        lon        = _to_float(rec.get("lon") or rec.get("longitude"))
        raw_status = str(rec.get("status", "unknown"))

        # Known state fields
        battery_level   = _to_int(rec.get("battery_level"))
        signal_strength = _to_int(rec.get("signal_strength"))
        error_code      = str(rec.get("error_code", "")).strip() or None

        # Known position extras
        altitude = _to_float(rec.get("altitude"))
        heading  = _to_float(rec.get("heading"))
        speed    = _to_float(rec.get("speed"))

        # Device-level metadata fields (stored in devices table)
        external_key = str(rec.get("external_key", "")).strip() or None
        ip_address   = str(rec.get("ip_address", "")).strip() or None
        port         = _to_int(rec.get("port"))
        priority     = _to_int(rec.get("priority"))
        device_type  = str(rec.get("device_type", "")).strip() or None
        description  = str(rec.get("description", "")).strip() or None
        icon_path    = str(rec.get("icon_path", "")).strip() or None

        # Arbitrary custom metrics → extra_state JSONB
        extra_state = {
            k: v for k, v in rec.items()
            if k not in _ALL_KNOWN
        }
        # Explicit JSON text is safer with asyncpg prepared statements.
        # Without ::jsonb casts PostgreSQL may fail with:
        # "could not determine data type of parameter $6".
        extra_state_json = json.dumps(extra_state, ensure_ascii=False, default=str)

        # All non-fixed fields → extra_data in ext_devices (for reference)
        extra_data = {
            k: v for k, v in rec.items()
            if k not in _FIXED_FIELDS
        }

        # 1. Upsert into ext_devices (staging table)
        await conn.execute(
            """INSERT INTO ext_devices
                   (name, online, status, latitude, longitude, extra_data, received_at, synced_at)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $7)
               ON CONFLICT (name) DO UPDATE SET
                   online      = EXCLUDED.online,
                   status      = EXCLUDED.status,
                   latitude    = EXCLUDED.latitude,
                   longitude   = EXCLUDED.longitude,
                   extra_data  = EXCLUDED.extra_data,
                   received_at = EXCLUDED.received_at,
                   synced_at   = EXCLUDED.synced_at""",
            name, online, raw_status, lat, lon,
            json.dumps(extra_data, ensure_ascii=False, default=str),  # text cast — safe
            now,
        )

        # 2. Find in main devices table by name (case-insensitive)
        dev = await conn.fetchrow(
            "SELECT id FROM devices WHERE LOWER(name) = LOWER($1)", name
        )

        if dev:
            dev_id: int = dev["id"]

            # Update devices table (operational metadata from external source)
            await conn.execute(
                """UPDATE devices SET
                       ip_address   = COALESCE($1::text, ip_address),
                       external_key = COALESCE($2::text, external_key),
                       port         = COALESCE($3::integer, port),
                       priority     = COALESCE($4::smallint, priority),
                       device_type  = COALESCE($5::text, device_type),
                       description  = CASE WHEN $6::text IS NOT NULL AND description IS NULL
                                          THEN $6::text ELSE description END,
                       icon_path    = CASE WHEN $7::text IS NOT NULL AND icon_path IS NULL
                                          THEN $7::text ELSE icon_path END,
                       updated_at   = $8::timestamptz
                   WHERE id = $9::integer""",
                ip_address, external_key, port, priority, device_type,
                description, icon_path, now, dev_id,
            )

            # Update device_states (COALESCE keeps existing value when new is NULL)
            # Pass extra_state as Python dict — asyncpg JSONB codec handles encoding
            await conn.execute(
                """UPDATE device_states
                   SET online_status    = $1,
                       operational_mode = $2,
                       battery_level    = COALESCE($3::smallint, battery_level),
                       signal_strength  = COALESCE($4::smallint, signal_strength),
                       error_code       = COALESCE($5::text, error_code),
                       extra_state      = COALESCE(extra_state, '{}'::jsonb) || $6::jsonb,
                       last_seen        = $7::timestamptz,
                       last_heartbeat   = $7::timestamptz,
                       updated_at       = $7::timestamptz
                   WHERE device_id = $8::integer""",
                online, mode,
                battery_level, signal_strength, error_code,
                extra_state_json,
                now, dev_id,
            )

            # Update device_positions
            if lat is not None and lon is not None:
                res = await conn.execute(
                    """UPDATE device_positions
                       SET latitude    = $1,
                           longitude   = $2,
                           altitude    = COALESCE($3::numeric, altitude),
                           heading     = COALESCE($4::numeric, heading),
                           speed       = COALESCE($5::numeric, speed),
                           recorded_at = $6::timestamptz
                       WHERE device_id = $7::integer AND is_current = TRUE""",
                    lat, lon, altitude, heading, speed, now, dev_id,
                )
                if res == "UPDATE 0":
                    await conn.execute(
                        """INSERT INTO device_positions
                               (device_id, latitude, longitude, altitude, heading, speed, is_current, recorded_at)
                           VALUES ($1, $2, $3, $4, $5, $6, TRUE, $7)""",
                        dev_id, lat, lon, altitude or 0, heading, speed or 0, now,
                    )
            updated += 1

        else:
            # Create new device with ext_device category
            cat_id = await _ensure_ext_category(conn)

            dev_row = await conn.fetchrow(
                """INSERT INTO devices
                       (category_id, name, ip_address, external_key, port, priority,
                        device_type, description, icon_path, created_at, updated_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $10) RETURNING id""",
                cat_id, name, ip_address, external_key, port, priority,
                device_type, description, icon_path, now,
            )
            dev_id = dev_row["id"]

            if lat is not None and lon is not None:
                await conn.execute(
                    """INSERT INTO device_positions
                           (device_id, latitude, longitude, altitude, heading, speed, is_current, recorded_at)
                       VALUES ($1, $2, $3, $4, $5, $6, TRUE, $7)""",
                    dev_id, lat, lon, altitude or 0, heading, speed or 0, now,
                )

            await conn.execute(
                """INSERT INTO device_states
                       (device_id, online_status, operational_mode,
                        battery_level, signal_strength, error_code,
                        extra_state, last_seen, updated_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $8)""",
                dev_id, online, mode,
                battery_level, signal_strength, error_code,
                extra_state_json,
                now,
            )
            created += 1

    return {
        "received": len(records),
        "updated":  updated,
        "created":  created,
        "skipped":  skipped,
    }
