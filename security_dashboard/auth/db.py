import asyncpg
from auth.config import AUTH_DSN

_auth_pool: asyncpg.Pool | None = None


async def create_auth_pool() -> asyncpg.Pool:
    global _auth_pool
    _auth_pool = await asyncpg.create_pool(AUTH_DSN, min_size=2, max_size=5)
    return _auth_pool


async def close_auth_pool() -> None:
    global _auth_pool
    if _auth_pool:
        await _auth_pool.close()
        _auth_pool = None


def get_auth_pool() -> asyncpg.Pool:
    return _auth_pool
