import os
import json
import asyncpg
from fastapi import Request

DSN = os.getenv(
    "SENTINEL_DSN",
    "postgresql://sentinel_user@127.0.0.1:5440/sentinel_isskb",
)

_pool: asyncpg.Pool | None = None


async def _init_conn(conn: asyncpg.Connection):
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads,
        schema="pg_catalog", format="text"
    )
    await conn.set_type_codec(
        "json",  encoder=json.dumps, decoder=json.loads,
        schema="pg_catalog", format="text"
    )


async def create_pool() -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(DSN, min_size=2, max_size=10, init=_init_conn)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool | None:
    return _pool


async def get_db_conn(request: Request):
    async with request.app.state.db_pool.acquire() as conn:
        yield conn
