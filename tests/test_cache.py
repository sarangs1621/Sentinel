import time
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis_client
from app.models.check import Check
from app.models.enums import CheckStatus
from app.services.cache import CacheService
from app.workers.checkers import CheckOutcome
from app.workers.tasks import _aggregate_monitor_metrics, _perform_check, _yesterday_utc_midnight
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


# --- Helpers ---


async def _create_workspace(client: AsyncClient, headers: dict[str, str], name: str) -> dict:
    response = await client.post("/api/v1/workspaces", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _create_monitor(client: AsyncClient, headers: dict[str, str], workspace_id: str, **overrides) -> dict:
    payload = {
        "name": "Example",
        "monitor_type": "http",
        "target": "https://example.com",
        "check_interval_seconds": 60,
    }
    payload.update(overrides)
    response = await client.post(f"/api/v1/workspaces/{workspace_id}/monitors", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _record_check(
    client: AsyncClient, headers: dict[str, str], workspace_id: str, monitor_id: str, status_: str, **overrides
) -> dict:
    payload = {"status": status_}
    payload.update(overrides)
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/monitors/{monitor_id}/checks", json=payload, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _insert_check(
    db_session: AsyncSession,
    monitor_id: uuid.UUID,
    status: CheckStatus,
    response_time_ms: int | None,
    created_at: datetime,
) -> Check:
    check = Check(monitor_id=monitor_id, status=status, response_time_ms=response_time_ms, created_at=created_at)
    db_session.add(check)
    await db_session.commit()
    return check


# --- Dashboard cache ---


async def test_dashboard_cache_populated_and_invalidated_on_monitor_create(client: AsyncClient) -> None:
    headers = await auth_headers(client, "cache-owner1@example.com")
    workspace = await _create_workspace(client, headers, "Cache Co 1")
    workspace_id = workspace["id"]
    redis = get_redis_client()

    response = await client.get(f"/api/v1/workspaces/{workspace_id}/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    assert await redis.get(f"dashboard:{workspace_id}") is not None

    await _create_monitor(client, headers, workspace_id)
    assert await redis.get(f"dashboard:{workspace_id}") is None


async def test_dashboard_cache_invalidated_when_incident_opens(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await auth_headers(client, "cache-owner2@example.com")
    workspace = await _create_workspace(client, headers, "Cache Co 2")
    workspace_id = workspace["id"]
    monitor = await _create_monitor(client, headers, workspace_id, failure_threshold=1)
    monitor_id = uuid.UUID(monitor["id"])
    redis = get_redis_client()

    response = await client.get(f"/api/v1/workspaces/{workspace_id}/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    assert await redis.get(f"dashboard:{workspace_id}") is not None

    failure = CheckOutcome(CheckStatus.FAILURE, 100, "boom")
    with patch("app.workers.tasks.perform_health_check", new=AsyncMock(return_value=failure)):
        await _perform_check(monitor_id, session=db_session)

    assert await redis.get(f"dashboard:{workspace_id}") is None


# --- Monitor status cache ---


async def test_monitor_read_surfaces_cached_response_time(client: AsyncClient) -> None:
    headers = await auth_headers(client, "cache-owner3@example.com")
    workspace = await _create_workspace(client, headers, "Cache Co 3")
    monitor = await _create_monitor(client, headers, workspace["id"])

    assert monitor.get("last_response_time_ms") is None

    await _record_check(client, headers, workspace["id"], monitor["id"], "success", response_time_ms=123)

    detail = await client.get(f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["last_response_time_ms"] == 123

    listing = await client.get(f"/api/v1/workspaces/{workspace['id']}/monitors", headers=headers)
    assert listing.status_code == 200, listing.text
    [item] = [m for m in listing.json() if m["id"] == monitor["id"]]
    assert item["last_response_time_ms"] == 123


# --- Failure counter cache ---


async def test_failure_counter_in_redis_resets_on_recovery(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await auth_headers(client, "cache-owner4@example.com")
    workspace = await _create_workspace(client, headers, "Cache Co 4")
    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=2)
    monitor_id = uuid.UUID(monitor["id"])
    redis = get_redis_client()
    key = f"monitor:{monitor_id}:failure_count"

    failure = CheckOutcome(CheckStatus.FAILURE, 100, "boom")
    with patch("app.workers.tasks.perform_health_check", new=AsyncMock(return_value=failure)):
        await _perform_check(monitor_id, session=db_session)
        assert await redis.get(key) == "1"

        await _perform_check(monitor_id, session=db_session)
        assert await redis.get(key) == "2"

    detail = await client.get(f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}", headers=headers)
    assert detail.json()["status"] == "down"
    assert detail.json()["consecutive_failures"] == 2

    success = CheckOutcome(CheckStatus.SUCCESS, 30, None)
    with patch("app.workers.tasks.perform_health_check", new=AsyncMock(return_value=success)):
        await _perform_check(monitor_id, session=db_session)

    assert await redis.get(key) is None

    detail = await client.get(f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}", headers=headers)
    assert detail.json()["status"] == "up"
    assert detail.json()["consecutive_failures"] == 0


# --- Analytics cache ---


async def test_latency_analytics_cache_invalidated_by_aggregation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await auth_headers(client, "cache-owner5@example.com")
    workspace = await _create_workspace(client, headers, "Cache Co 5")
    monitor = await _create_monitor(client, headers, workspace["id"])
    monitor_id = uuid.UUID(monitor["id"])

    now = datetime.now(UTC)
    start = now - timedelta(hours=1)
    params = {"start": start.isoformat(), "end": now.isoformat()}
    url = f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/metrics/latency"

    response = await client.get(url, params=params, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["total_checks"] == 0

    await _insert_check(db_session, monitor_id, CheckStatus.SUCCESS, 150, now - timedelta(minutes=30))

    cached = await client.get(url, params=params, headers=headers)
    assert cached.json()["total_checks"] == 0  # stale cached value, not yet invalidated

    await _aggregate_monitor_metrics(monitor_id, _yesterday_utc_midnight(), session=db_session)

    refreshed = await client.get(url, params=params, headers=headers)
    assert refreshed.json()["total_checks"] == 1


# --- Rate limiting ---


async def test_rate_limit_returns_429_when_exceeded(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = await auth_headers(client, "cache-owner6@example.com")

    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_REQUESTS", 3)
    monkeypatch.setattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)

    for _ in range(3):
        response = await client.get("/api/v1/workspaces", headers=headers)
        assert response.status_code == 200, response.text

    response = await client.get("/api/v1/workspaces", headers=headers)
    assert response.status_code == 429, response.text
    assert "Retry-After" in response.headers
    assert response.json()["detail"] == "Rate limit exceeded. Please try again later."


# --- Graceful degradation when Redis is unreachable ---


class _BrokenRedis:
    """Stand-in for a Redis client whose every call fails, as if Redis were down."""

    async def get(self, *args: object, **kwargs: object) -> None:
        raise RedisError("connection refused")

    async def set(self, *args: object, **kwargs: object) -> None:
        raise RedisError("connection refused")

    async def delete(self, *args: object, **kwargs: object) -> None:
        raise RedisError("connection refused")

    async def exists(self, *args: object, **kwargs: object) -> None:
        raise RedisError("connection refused")

    async def incr(self, *args: object, **kwargs: object) -> None:
        raise RedisError("connection refused")

    async def expire(self, *args: object, **kwargs: object) -> None:
        raise RedisError("connection refused")

    async def ttl(self, *args: object, **kwargs: object) -> None:
        raise RedisError("connection refused")


async def test_cache_service_degrades_gracefully_when_redis_unreachable() -> None:
    cache = CacheService(_BrokenRedis())  # type: ignore[arg-type]
    workspace_id = uuid.uuid4()
    monitor_id = uuid.uuid4()

    assert await cache.get_dashboard(workspace_id) is None
    await cache.set_dashboard(workspace_id, {"foo": "bar"})
    await cache.invalidate_dashboard(workspace_id)

    assert await cache.get_monitor_status(monitor_id) is None

    assert await cache.increment_failure_count(monitor_id, seed=4) == 5
    await cache.reset_failure_count(monitor_id)

    assert await cache.get_analytics("latency", monitor_id, "params") is None
    await cache.set_analytics("latency", monitor_id, "params", {"total_checks": 0})
    await cache.invalidate_analytics(monitor_id)

    allowed, retry_after = await cache.check_rate_limit("ratelimit:test", 1, 60)
    assert allowed is True
    assert retry_after == 0


async def test_token_denylist_and_login_failure_degrade_gracefully_when_redis_unreachable() -> None:
    cache = CacheService(_BrokenRedis())  # type: ignore[arg-type]

    # denylist_token: RedisError on set() is swallowed.
    await cache.denylist_token("some-jti", int(time.time()) + 3600)

    # is_token_denylisted: RedisError on exists() -> not denylisted.
    assert await cache.is_token_denylisted("some-jti") is False

    # record_login_failure: RedisError on incr() -> 0.
    assert await cache.record_login_failure("user@example.com") == 0

    # get_login_failure_count: RedisError on get() -> 0.
    assert await cache.get_login_failure_count("user@example.com") == 0


async def test_denylist_token_with_past_expiry_is_noop() -> None:
    cache = CacheService(get_redis_client())
    jti = str(uuid.uuid4())

    await cache.denylist_token(jti, int(time.time()) - 10)

    assert await cache.is_token_denylisted(jti) is False


async def test_check_rate_limit_blocks_after_limit_reached() -> None:
    cache = CacheService(get_redis_client())
    key = f"ratelimit:test:{uuid.uuid4()}"

    allowed, retry_after = await cache.check_rate_limit(key, 2, 60)
    assert allowed is True
    assert retry_after == 0

    allowed, retry_after = await cache.check_rate_limit(key, 2, 60)
    assert allowed is True
    assert retry_after == 0

    allowed, retry_after = await cache.check_rate_limit(key, 2, 60)
    assert allowed is False
    assert retry_after > 0
