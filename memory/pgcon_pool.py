from __future__ import annotations

import asyncio
import os
import sys
from psycopg_pool import AsyncConnectionPool

from config import PG_POOL_MIN_SIZE, PG_POOL_MAX_SIZE, PG_POOL_MAX_IDLE

_pool: AsyncConnectionPool | None = None


def _build_dsn() -> str:
    """从环境变量拼接 PostgreSQL 连接字符串。"""
    host = os.getenv("postgres_host", "127.0.0.1")
    port = os.getenv("postgres_port", "5432")

    return (
        f"host={host} port={port}"
        f" dbname={os.getenv('postgres_db', '')}"
        f" user={os.getenv('postgres_user', '')}"
        f" password={os.getenv('postgres_password', '')}"
    )


async def init_pool() -> None:
    """在 FastAPI 启动时调用，预创建连接池并打开 min_size 个连接。"""
    global _pool
    # Windows 默认 ProactorEventLoop 不支持 psycopg async，需切换为 Selector
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    _pool = AsyncConnectionPool(
        conninfo=_build_dsn(),
        min_size=PG_POOL_MIN_SIZE,
        max_size=PG_POOL_MAX_SIZE,
        max_idle=PG_POOL_MAX_IDLE,
        open=False,
    )
    await _pool.open(wait=True)


def get_pool() -> AsyncConnectionPool:
    """获取已初始化的连接池。必须在 init_pool() 之后调用。"""
    assert _pool is not None, "连接池未初始化，请先调用 init_pool()"
    return _pool


async def close_pool() -> None:
    """关闭连接池，释放所有连接。在 FastAPI lifespan 退出时调用。"""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
