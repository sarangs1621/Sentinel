from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.redis import create_redis_client


@asynccontextmanager
async def worker_session() -> AsyncIterator[AsyncSession]:
    """A short-lived engine/session for a single Celery task run.

    Each task gets its own engine (rather than reusing `app.db.session.engine`)
    because Celery tasks run inside their own `asyncio.run()` event loop, and
    asyncpg connections can't be shared across event loops.
    """
    engine = create_async_engine(settings.DATABASE_URL, future=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()


@asynccontextmanager
async def worker_redis() -> AsyncIterator[Redis]:
    """A short-lived Redis client for a single Celery task run.

    Mirrors `worker_session`: each task gets its own client (rather than reusing
    `app.core.redis.redis_client`) because Celery tasks run inside their own
    `asyncio.run()` event loop, and redis-py connections can't be shared across
    event loops.
    """
    client = create_redis_client()
    try:
        yield client
    finally:
        await client.aclose()
