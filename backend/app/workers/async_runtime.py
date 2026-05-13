from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from contextlib import suppress
from typing import TypeVar

from app.core.redis import close_redis_client
from app.db.session import dispose_db_engine

T = TypeVar("T")


def run_celery_async(awaitable: Awaitable[T]) -> T:
    return asyncio.run(_run_celery_async(awaitable))


async def _run_celery_async(awaitable: Awaitable[T]) -> T:
    try:
        return await awaitable
    finally:
        with suppress(Exception):
            await close_redis_client()
        with suppress(Exception):
            await dispose_db_engine()