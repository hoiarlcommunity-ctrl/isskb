import asyncio, sys
sys.path.insert(0, ".")
from database.connection import DSN, _init_conn
import asyncpg

async def clear():
    conn = await asyncpg.connect(DSN)
    await _init_conn(conn)
    for tbl in ["incident_comments","incidents","device_metrics","device_states","device_positions","devices","operators"]:
        try:
            await conn.execute(f"DELETE FROM {tbl}")
            print(f"  cleared {tbl}")
        except Exception as e:
            print(f"  skip {tbl}: {e}")
    try:
        await conn.execute("DELETE FROM device_categories WHERE code LIKE 'cat_%' OR code = 'ext_device'")
        print("  cleared device_categories")
    except Exception as e:
        print(f"  skip device_categories: {e}")
    await conn.close()
    print("Done")

asyncio.run(clear())
