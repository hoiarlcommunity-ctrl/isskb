"""
DB watcher — обнаруживает изменения, сделанные напрямую в БД (pgAdmin, psql),
и рассылает device_updated по WebSocket, чтобы фронтенд оставался актуальным.

Опрашивает БД каждые 10 секунд.
Сравнивает только поля состояния и атрибутов — позиции исключены
(ими занимается simulator каждые 2 секунды).
"""
import asyncio

import asyncpg
from database.connection import DSN
from websocket.manager import manager

POLL_INTERVAL = 10  # секунд

# Поля, изменение которых считается "событием"
_WATCH_FIELDS = (
    "name", "responsible_person", "icon_path", "description",
    "online_status", "operational_mode", "battery_level",
    "signal_strength", "error_code",
)

_snapshot: dict[int, tuple] = {}


async def db_watcher_loop() -> None:
    global _snapshot
    print("[WATCHER] DB watcher starting...")
    await asyncio.sleep(8)  # дать серверу полностью подняться

    # Импорт здесь, чтобы не было circular import при старте
    from api.devices import _DEVICE_SELECT, _serialize

    query = _DEVICE_SELECT + " ORDER BY d.id"

    while True:
        try:
            conn = await asyncpg.connect(DSN)
            try:
                rows = await conn.fetch(query)
            finally:
                await conn.close()

            current: dict[int, asyncpg.Record] = {r["id"]: r for r in rows}

            if not _snapshot:
                # Первый прогон — строим baseline без броадкастов
                _snapshot = {
                    dev_id: _key(r)
                    for dev_id, r in current.items()
                }
            else:
                changed: list[dict] = []

                for dev_id, row in current.items():
                    k = _key(row)
                    if _snapshot.get(dev_id) != k:
                        _snapshot[dev_id] = k
                        changed.append(_serialize(row))

                # Устройства удалённые из БД — убираем из снапшота
                for dev_id in list(_snapshot):
                    if dev_id not in current:
                        del _snapshot[dev_id]

                if changed and manager.client_count > 0:
                    for dev in changed:
                        await manager.broadcast("device_updated", dev)
                    print(f"[WATCHER] {len(changed)} device(s) changed → broadcasted")

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[WATCHER] Error: {exc}")

        await asyncio.sleep(POLL_INTERVAL)


def _key(row: asyncpg.Record) -> tuple:
    return tuple(row[f] for f in _WATCH_FIELDS if f in row.keys())
