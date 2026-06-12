import logging

from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)


def create_redis_client() -> Redis:
    """Build a new Redis client bound to `settings.REDIS_URL`.

    Used directly by Celery workers (each task run gets its own client, mirroring
    `worker_session`, since asyncpg/redis connections can't cross event loops created by
    repeated `asyncio.run()` calls).
    """
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)


redis_client: Redis = create_redis_client()


def get_redis_client() -> Redis:
    """Return the process-wide Redis client used by the FastAPI app."""
    return redis_client
