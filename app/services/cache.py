import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis import get_redis_client
from app.models.enums import MonitorStatus

logger = logging.getLogger(__name__)

DASHBOARD_CACHE_TTL_SECONDS = 300
ANALYTICS_CACHE_TTL_SECONDS = 300
MONITOR_STATUS_CACHE_TTL_SECONDS = 60


class CacheService:
    """Thin wrapper around Redis for Phase 8's caching/derived-state layer.

    Postgres remains the source of truth: every method here is best-effort. If Redis
    is unreachable, reads return `None`/empty (treated as a cache miss) and writes are
    silently skipped (logged at warning level) so the rest of the request can proceed
    against Postgres alone.
    """

    def __init__(self, redis: Redis | None = None) -> None:
        self.redis = redis if redis is not None else get_redis_client()

    # ------------------------------------------------------------------
    # Dashboard cache: dashboard:{workspace_id}, TTL 300s
    # ------------------------------------------------------------------
    async def get_dashboard(self, workspace_id: uuid.UUID) -> dict[str, Any] | None:
        return await self._get_json(f"dashboard:{workspace_id}")

    async def set_dashboard(self, workspace_id: uuid.UUID, data: dict[str, Any]) -> None:
        await self._set_json(f"dashboard:{workspace_id}", data, DASHBOARD_CACHE_TTL_SECONDS)

    async def invalidate_dashboard(self, workspace_id: uuid.UUID) -> None:
        await self._delete(f"dashboard:{workspace_id}")

    # ------------------------------------------------------------------
    # Monitor status cache: monitor:{monitor_id}:status, TTL 60s
    # ------------------------------------------------------------------
    async def get_monitor_status(self, monitor_id: uuid.UUID) -> dict[str, Any] | None:
        return await self._get_json(f"monitor:{monitor_id}:status")

    async def set_monitor_status(
        self,
        monitor_id: uuid.UUID,
        status: MonitorStatus,
        checked_at: datetime,
        response_time_ms: int | None,
    ) -> None:
        await self._set_json(
            f"monitor:{monitor_id}:status",
            {
                "last_status": status.value,
                "last_checked_at": checked_at.isoformat(),
                "last_response_time_ms": response_time_ms,
            },
            MONITOR_STATUS_CACHE_TTL_SECONDS,
        )

    # ------------------------------------------------------------------
    # Consecutive failure counter: monitor:{monitor_id}:failure_count
    # ------------------------------------------------------------------
    async def increment_failure_count(self, monitor_id: uuid.UUID, seed: int) -> int:
        """Increment the Redis failure counter, seeding it from `seed` (the monitor's
        current `consecutive_failures` column) if the key doesn't exist yet.

        Falls back to `seed + 1` if Redis is unavailable, preserving the old
        Postgres-only behavior.
        """
        key = f"monitor:{monitor_id}:failure_count"
        try:
            if not await self.redis.exists(key):
                await self.redis.set(key, seed)
            return await self.redis.incr(key)
        except RedisError:
            logger.warning("Redis unavailable for failure counter %s; falling back to DB value", monitor_id)
            return seed + 1

    async def reset_failure_count(self, monitor_id: uuid.UUID) -> None:
        await self._delete(f"monitor:{monitor_id}:failure_count")

    # ------------------------------------------------------------------
    # Analytics cache: analytics:{kind}:{monitor_id}:v{version}:{params}, TTL 300s
    # Invalidated by bumping analytics:version:{monitor_id} (old entries expire via TTL).
    # ------------------------------------------------------------------
    async def get_analytics(self, kind: str, monitor_id: uuid.UUID, params: str) -> dict[str, Any] | list[Any] | None:
        version = await self._analytics_version(monitor_id)
        return await self._get_json(self._analytics_key(kind, monitor_id, version, params))

    async def set_analytics(
        self, kind: str, monitor_id: uuid.UUID, params: str, data: dict[str, Any] | list[Any]
    ) -> None:
        version = await self._analytics_version(monitor_id)
        await self._set_json(self._analytics_key(kind, monitor_id, version, params), data, ANALYTICS_CACHE_TTL_SECONDS)

    async def invalidate_analytics(self, monitor_id: uuid.UUID) -> None:
        try:
            await self.redis.incr(f"analytics:version:{monitor_id}")
        except RedisError:
            logger.warning("Redis unavailable to invalidate analytics cache for monitor %s", monitor_id)

    async def _analytics_version(self, monitor_id: uuid.UUID) -> int:
        try:
            raw = await self.redis.get(f"analytics:version:{monitor_id}")
            return int(raw) if raw is not None else 0
        except (RedisError, ValueError):
            return 0

    @staticmethod
    def _analytics_key(kind: str, monitor_id: uuid.UUID, version: int, params: str) -> str:
        return f"analytics:{kind}:{monitor_id}:v{version}:{params}"

    # ------------------------------------------------------------------
    # Rate limiting: fixed-window counter on a caller-supplied key
    # ------------------------------------------------------------------
    async def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Increment the counter at `key` and report whether it's within `limit`.

        Returns `(allowed, retry_after_seconds)`. Fails open (allowed=True) if Redis
        is unavailable.
        """
        try:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, window_seconds)
            if count <= limit:
                return True, 0
            ttl = await self.redis.ttl(key)
            return False, ttl if ttl > 0 else window_seconds
        except RedisError:
            return True, 0

    # ------------------------------------------------------------------
    # Access-token denylist: denylist:{jti}, TTL = remaining token lifetime
    # ------------------------------------------------------------------
    async def denylist_token(self, jti: str, exp: int) -> None:
        """Denylist a token's `jti` until its `exp` (unix timestamp) passes."""
        ttl = exp - int(time.time())
        if ttl <= 0:
            return
        try:
            await self.redis.set(f"denylist:{jti}", "1", ex=ttl)
        except RedisError:
            logger.warning("Redis unavailable to denylist token %s", jti)

    async def is_token_denylisted(self, jti: str) -> bool:
        try:
            return bool(await self.redis.exists(f"denylist:{jti}"))
        except RedisError:
            return False

    # ------------------------------------------------------------------
    # Login failure tracking: loginfail:{email}, TTL = LOGIN_LOCKOUT_WINDOW_SECONDS
    # ------------------------------------------------------------------
    async def record_login_failure(self, email: str) -> int:
        key = f"loginfail:{email}"
        try:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, settings.LOGIN_LOCKOUT_WINDOW_SECONDS)
            return count
        except RedisError:
            return 0

    async def get_login_failure_count(self, email: str) -> int:
        try:
            raw = await self.redis.get(f"loginfail:{email}")
            return int(raw) if raw is not None else 0
        except (RedisError, ValueError):
            return 0

    async def reset_login_failures(self, email: str) -> None:
        await self._delete(f"loginfail:{email}")

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------
    async def _get_json(self, key: str) -> Any | None:
        try:
            raw = await self.redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except (RedisError, ValueError):
            return None

    async def _set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        try:
            await self.redis.set(key, json.dumps(value), ex=ttl_seconds)
        except RedisError:
            logger.warning("Redis unavailable to set cache key %s", key)

    async def _delete(self, key: str) -> None:
        try:
            await self.redis.delete(key)
        except RedisError:
            logger.warning("Redis unavailable to delete cache key %s", key)
