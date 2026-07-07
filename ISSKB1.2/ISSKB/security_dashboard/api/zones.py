from fastapi import APIRouter, Depends
from database.connection import get_db_conn
import asyncpg

router = APIRouter(prefix="/api/zones", tags=["zones"])


@router.get("")
async def list_zones(conn: asyncpg.Connection = Depends(get_db_conn)):
    rows = await conn.fetch("""
        SELECT z.id, z.name, z.code, z.color, z.description,
               z.lat_center, z.lon_center, z.radius_m,
               COUNT(d.id) AS device_count
        FROM zones z
        LEFT JOIN devices d ON d.zone_id = z.id
        GROUP BY z.id
        ORDER BY z.name
    """)
    return [dict(r) for r in rows]


@router.get("/stats")
async def system_stats(conn: asyncpg.Connection = Depends(get_db_conn)):
    stats = await conn.fetchrow("""
        SELECT
            COUNT(*)                                             AS total,
            COUNT(*) FILTER (WHERE ds.online_status = TRUE)     AS online,
            COUNT(*) FILTER (WHERE ds.online_status = FALSE)    AS offline,
            COUNT(*) FILTER (WHERE ds.operational_mode='alarm') AS alarm,
            COUNT(*) FILTER (WHERE ds.operational_mode='warning') AS warning,
            COUNT(*) FILTER (WHERE ds.operational_mode='maintenance') AS maintenance
        FROM devices d
        LEFT JOIN device_states ds ON ds.device_id = d.id
    """)
    inc = await conn.fetchrow("""
        SELECT
            COUNT(*)                                              AS total_incidents,
            COUNT(*) FILTER (WHERE status = 'open')              AS open_incidents,
            COUNT(*) FILTER (WHERE severity = 'critical' AND status NOT IN ('resolved','false_alarm')) AS critical_incidents
        FROM incidents
        WHERE status NOT IN ('resolved','false_alarm')
    """)
    return {**dict(stats), **dict(inc)}
