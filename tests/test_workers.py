import asyncio
import socket
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ConnectError, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CheckStatus, MonitorType
from app.workers.checkers import CheckOutcome, perform_health_check
from app.workers.db import worker_redis, worker_session
from app.workers.tasks import _get_due_monitor_ids, _perform_check
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


# --- Checkers ---


async def test_check_http_success(respx_mock) -> None:
    respx_mock.get("https://example.com/health").mock(return_value=Response(200))

    outcome = await perform_health_check(MonitorType.HTTP, "https://example.com/health")

    assert outcome.status == CheckStatus.SUCCESS
    assert outcome.error_message is None
    assert outcome.response_time_ms is not None


async def test_check_http_failure_status(respx_mock) -> None:
    respx_mock.get("https://example.com/down").mock(return_value=Response(503))

    outcome = await perform_health_check(MonitorType.HTTP, "https://example.com/down")

    assert outcome.status == CheckStatus.FAILURE
    assert outcome.error_message == "HTTP 503"


async def test_check_http_connection_error(respx_mock) -> None:
    respx_mock.get("https://unreachable.example.com").mock(side_effect=ConnectError("boom"))

    outcome = await perform_health_check(MonitorType.HTTP, "https://unreachable.example.com")

    assert outcome.status == CheckStatus.FAILURE
    assert outcome.error_message is not None


async def test_check_tcp_success() -> None:
    server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        outcome = await perform_health_check(MonitorType.TCP, f"127.0.0.1:{port}")
    finally:
        server.close()
        await server.wait_closed()

    assert outcome.status == CheckStatus.SUCCESS
    assert outcome.error_message is None
    assert outcome.response_time_ms is not None


async def test_check_tcp_failure() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    outcome = await perform_health_check(MonitorType.TCP, f"127.0.0.1:{port}")

    assert outcome.status == CheckStatus.FAILURE
    assert outcome.error_message is not None


async def test_check_ping_success() -> None:
    outcome = await perform_health_check(MonitorType.PING, "127.0.0.1")

    assert outcome.status == CheckStatus.SUCCESS
    assert outcome.error_message is None


class _FakeProcess:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        return b"", b""


async def test_check_ping_failure() -> None:
    fake_exec = AsyncMock(return_value=_FakeProcess(returncode=1))
    with patch("app.workers.checkers.asyncio.create_subprocess_exec", new=fake_exec):
        outcome = await perform_health_check(MonitorType.PING, "127.0.0.1")

    assert outcome.status == CheckStatus.FAILURE
    assert outcome.error_message is not None


# --- Scheduler / dispatch ---


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


async def test_due_monitor_no_longer_due_after_check(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await auth_headers(client, "worker-owner1@example.com")
    workspace = await _create_workspace(client, headers, "Worker Co 1")
    monitor = await _create_monitor(client, headers, workspace["id"])
    monitor_id = uuid.UUID(monitor["id"])

    due_ids = await _get_due_monitor_ids(session=db_session)
    assert monitor_id in due_ids

    success = CheckOutcome(CheckStatus.SUCCESS, 50, None)
    with patch("app.workers.tasks.perform_health_check", new=AsyncMock(return_value=success)):
        await _perform_check(monitor_id, session=db_session)

    due_ids = await _get_due_monitor_ids(session=db_session)
    assert monitor_id not in due_ids


async def test_perform_check_drives_incident_lifecycle(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await auth_headers(client, "worker-owner2@example.com")
    workspace = await _create_workspace(client, headers, "Worker Co 2")
    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=2)
    monitor_id = uuid.UUID(monitor["id"])

    failure = CheckOutcome(CheckStatus.FAILURE, 100, "connection refused")
    with patch("app.workers.tasks.perform_health_check", new=AsyncMock(return_value=failure)):
        await _perform_check(monitor_id, session=db_session)
        await _perform_check(monitor_id, session=db_session)

    detail = await client.get(f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}", headers=headers)
    assert detail.json()["status"] == "down"
    assert detail.json()["consecutive_failures"] == 2

    incidents = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents", headers=headers)
    assert len(incidents.json()) == 1
    assert incidents.json()[0]["status"] == "open"

    success = CheckOutcome(CheckStatus.SUCCESS, 30, None)
    with patch("app.workers.tasks.perform_health_check", new=AsyncMock(return_value=success)):
        await _perform_check(monitor_id, session=db_session)

    detail = await client.get(f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}", headers=headers)
    assert detail.json()["status"] == "up"
    assert detail.json()["consecutive_failures"] == 0

    incidents = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents", headers=headers)
    assert incidents.json()[0]["status"] == "resolved"


async def test_perform_check_ignores_inactive_monitor(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await auth_headers(client, "worker-owner3@example.com")
    workspace = await _create_workspace(client, headers, "Worker Co 3")
    monitor = await _create_monitor(client, headers, workspace["id"])
    monitor_id = uuid.UUID(monitor["id"])

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}",
        json={"is_active": False},
        headers=headers,
    )
    assert response.status_code == 200

    mock_check = AsyncMock(return_value=CheckOutcome(CheckStatus.SUCCESS, 10, None))
    with patch("app.workers.tasks.perform_health_check", new=mock_check):
        await _perform_check(monitor_id, session=db_session)

    mock_check.assert_not_called()


async def test_perform_check_ignores_unknown_monitor(db_session: AsyncSession) -> None:
    mock_check = AsyncMock(return_value=CheckOutcome(CheckStatus.SUCCESS, 10, None))
    with patch("app.workers.tasks.perform_health_check", new=mock_check):
        await _perform_check(uuid.uuid4(), session=db_session)

    mock_check.assert_not_called()


# --- Worker session/connection helpers ---


async def test_worker_session_yields_usable_session() -> None:
    async with worker_session() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1


async def test_worker_redis_yields_usable_client() -> None:
    async with worker_redis() as redis:
        await redis.set("worker-redis-test-key", "value")
        assert await redis.get("worker-redis-test-key") == "value"
