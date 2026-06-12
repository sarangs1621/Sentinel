import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.check import Check
from app.models.enums import CheckStatus, IncidentSeverity, IncidentStatus, MetricPeriod
from app.models.incident import Incident
from app.models.metric_snapshot import MetricSnapshot
from app.repositories.metric_snapshot import MetricSnapshotRepository
from app.services.metrics import MetricsService
from app.workers.tasks import _aggregate_monitor_metrics, _get_aggregation_monitor_ids, _yesterday_utc_midnight
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


async def _insert_incident(
    db_session: AsyncSession,
    workspace_id: uuid.UUID,
    monitor_id: uuid.UUID,
    status: IncidentStatus,
    created_at: datetime,
    resolved_at: datetime | None,
) -> Incident:
    incident = Incident(
        workspace_id=workspace_id,
        monitor_id=monitor_id,
        title="Test incident",
        status=status,
        severity=IncidentSeverity.MAJOR,
        created_at=created_at,
        resolved_at=resolved_at,
    )
    db_session.add(incident)
    await db_session.commit()
    return incident


async def _insert_snapshot(
    db_session: AsyncSession,
    monitor_id: uuid.UUID,
    workspace_id: uuid.UUID,
    period_start: datetime,
) -> MetricSnapshot:
    snapshot = MetricSnapshot(
        monitor_id=monitor_id,
        workspace_id=workspace_id,
        period_type=MetricPeriod.DAILY,
        period_start=period_start,
        period_end=period_start + timedelta(days=1),
    )
    db_session.add(snapshot)
    await db_session.commit()
    return snapshot


# --- Latency metrics ---


async def test_latency_metrics_with_checks(client: AsyncClient) -> None:
    headers = await auth_headers(client, "metrics-owner1@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 1")
    monitor = await _create_monitor(client, headers, workspace["id"])

    for response_time_ms in (100, 200, 300, 400, 500):
        await _record_check(
            client, headers, workspace["id"], monitor["id"], "success", response_time_ms=response_time_ms
        )

    response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/metrics/latency", headers=headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_checks"] == 5
    assert body["avg_response_time_ms"] == pytest.approx(300.0)
    assert body["min_response_time_ms"] == 100
    assert body["max_response_time_ms"] == 500
    assert body["p50_response_time_ms"] == pytest.approx(300.0)
    assert body["p95_response_time_ms"] == pytest.approx(480.0)
    assert body["p99_response_time_ms"] == pytest.approx(496.0)


async def test_latency_metrics_empty_range(client: AsyncClient) -> None:
    headers = await auth_headers(client, "metrics-owner2@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 2")
    monitor = await _create_monitor(client, headers, workspace["id"])

    response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/metrics/latency", headers=headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_checks"] == 0
    for field in (
        "avg_response_time_ms",
        "min_response_time_ms",
        "max_response_time_ms",
        "p50_response_time_ms",
        "p95_response_time_ms",
        "p99_response_time_ms",
    ):
        assert body[field] is None


# --- Uptime / SLA reporting ---


async def test_uptime_report_check_based(client: AsyncClient) -> None:
    headers = await auth_headers(client, "metrics-owner3@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 3")
    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=10)

    for status_ in ("success", "success", "failure", "success", "failure"):
        await _record_check(client, headers, workspace["id"], monitor["id"], status_)

    response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/metrics/uptime", headers=headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_checks"] == 5
    assert body["successful_checks"] == 3
    assert body["failed_checks"] == 2
    assert body["check_pass_ratio"] == pytest.approx(60.0)
    assert body["incidents_count"] == 0
    assert body["uptime_percentage"] == pytest.approx(100.0)
    assert body["total_downtime_seconds"] == pytest.approx(0.0)


async def test_uptime_report_time_based_with_resolved_incident(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await auth_headers(client, "metrics-owner4@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 4")
    monitor = await _create_monitor(client, headers, workspace["id"])

    now = datetime.now(UTC)
    start = now - timedelta(hours=24)
    await _insert_incident(
        db_session,
        workspace_id=uuid.UUID(workspace["id"]),
        monitor_id=uuid.UUID(monitor["id"]),
        status=IncidentStatus.RESOLVED,
        created_at=now - timedelta(hours=2),
        resolved_at=now - timedelta(hours=1),
    )

    response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/metrics/uptime",
        params={"start": start.isoformat(), "end": now.isoformat()},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["incidents_count"] == 1
    assert body["total_downtime_seconds"] == pytest.approx(3600, abs=5)
    expected_uptime = (86400 - 3600) / 86400 * 100
    assert body["uptime_percentage"] == pytest.approx(expected_uptime, abs=0.01)


async def test_uptime_report_open_incident_downtime_extends_to_now(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await auth_headers(client, "metrics-owner5@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 5")
    monitor = await _create_monitor(client, headers, workspace["id"])

    now = datetime.now(UTC)
    await _insert_incident(
        db_session,
        workspace_id=uuid.UUID(workspace["id"]),
        monitor_id=uuid.UUID(monitor["id"]),
        status=IncidentStatus.OPEN,
        created_at=now - timedelta(minutes=30),
        resolved_at=None,
    )

    response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/metrics/uptime", headers=headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["incidents_count"] == 1
    assert body["total_downtime_seconds"] == pytest.approx(1800, abs=5)


async def test_uptime_invalid_range_returns_422(client: AsyncClient) -> None:
    headers = await auth_headers(client, "metrics-owner6@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 6")
    monitor = await _create_monitor(client, headers, workspace["id"])

    now = datetime.now(UTC)
    response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/metrics/uptime",
        params={"start": now.isoformat(), "end": now.isoformat()},
        headers=headers,
    )

    assert response.status_code == 422


async def test_uptime_report_cache_hit_returns_cached_value(client: AsyncClient) -> None:
    headers = await auth_headers(client, "metrics-owner6b@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 6b")
    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=10)

    await _record_check(client, headers, workspace["id"], monitor["id"], "success")

    now = datetime.now(UTC)
    start = now - timedelta(hours=1)
    params = {"start": start.isoformat(), "end": now.isoformat()}

    first = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/metrics/uptime",
        params=params,
        headers=headers,
    )
    assert first.status_code == 200, first.text

    second = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/metrics/uptime",
        params=params,
        headers=headers,
    )
    assert second.status_code == 200, second.text
    assert second.json() == first.json()


# --- Metric snapshots ---


async def test_snapshots_endpoint_lists_and_filters_by_date(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await auth_headers(client, "metrics-owner7@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 7")
    monitor = await _create_monitor(client, headers, workspace["id"])
    monitor_id = uuid.UUID(monitor["id"])
    workspace_id = uuid.UUID(workspace["id"])

    today_midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    day1 = today_midnight - timedelta(days=3)
    day2 = today_midnight - timedelta(days=2)
    day3 = today_midnight - timedelta(days=1)
    for period_start in (day1, day2, day3):
        await _insert_snapshot(db_session, monitor_id, workspace_id, period_start)

    response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/metrics/snapshots", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [datetime.fromisoformat(s["period_start"]) for s in body] == [day1, day2, day3]

    response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/metrics/snapshots",
        params={"start": day2.isoformat()},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [datetime.fromisoformat(s["period_start"]) for s in body] == [day2, day3]

    response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/metrics/snapshots",
        params={"end": day2.isoformat()},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [datetime.fromisoformat(s["period_start"]) for s in body] == [day1]


async def test_snapshots_cache_hit_returns_cached_value(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await auth_headers(client, "metrics-owner7b@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 7b")
    monitor = await _create_monitor(client, headers, workspace["id"])
    monitor_id = uuid.UUID(monitor["id"])
    workspace_id = uuid.UUID(workspace["id"])

    period_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    await _insert_snapshot(db_session, monitor_id, workspace_id, period_start)

    first = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/metrics/snapshots", headers=headers
    )
    assert first.status_code == 200, first.text

    second = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/metrics/snapshots", headers=headers
    )
    assert second.status_code == 200, second.text
    assert second.json() == first.json()


# --- Dashboard ---


async def test_dashboard_counts_across_monitors(client: AsyncClient) -> None:
    headers = await auth_headers(client, "metrics-owner8@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 8")

    pending_monitor = await _create_monitor(client, headers, workspace["id"], target="https://pending.example.com")

    down_monitor = await _create_monitor(
        client, headers, workspace["id"], target="https://down.example.com", failure_threshold=1
    )
    await _record_check(
        client, headers, workspace["id"], down_monitor["id"], "failure", response_time_ms=100
    )

    up_monitor = await _create_monitor(client, headers, workspace["id"], target="https://up.example.com")
    await _record_check(client, headers, workspace["id"], up_monitor["id"], "success", response_time_ms=50)

    response = await client.get(f"/api/v1/workspaces/{workspace['id']}/dashboard", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_monitors"] == 3
    assert body["monitor_status_counts"] == {"pending": 1, "up": 1, "down": 1}
    assert body["incident_status_counts"] == {"open": 1, "investigating": 0, "resolved": 0}
    assert body["total_checks"] == 2
    assert body["overall_check_pass_ratio"] == pytest.approx(50.0)
    assert body["avg_response_time_ms"] == pytest.approx(75.0)
    assert pending_monitor["status"] == "pending"


async def test_dashboard_cache_hit_returns_cached_value(client: AsyncClient) -> None:
    headers = await auth_headers(client, "metrics-owner8b@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 8b")
    monitor = await _create_monitor(client, headers, workspace["id"])
    await _record_check(client, headers, workspace["id"], monitor["id"], "success", response_time_ms=50)

    first = await client.get(f"/api/v1/workspaces/{workspace['id']}/dashboard", headers=headers)
    assert first.status_code == 200, first.text

    second = await client.get(f"/api/v1/workspaces/{workspace['id']}/dashboard", headers=headers)
    assert second.status_code == 200, second.text
    assert second.json() == first.json()


# --- Scheduled aggregation job ---


async def test_aggregate_daily_snapshot_creates_and_upserts(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await auth_headers(client, "metrics-owner9@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 9")
    monitor = await _create_monitor(client, headers, workspace["id"])
    monitor_id = uuid.UUID(monitor["id"])

    period_start = _yesterday_utc_midnight()
    for hour, response_time_ms in enumerate((100, 200, 300), start=1):
        await _insert_check(
            db_session, monitor_id, CheckStatus.SUCCESS, response_time_ms, period_start + timedelta(hours=hour)
        )

    await _aggregate_monitor_metrics(monitor_id, period_start, session=db_session)

    snapshot = await MetricSnapshotRepository(db_session).get_by_monitor_period(
        monitor_id, MetricPeriod.DAILY, period_start
    )
    assert snapshot is not None
    assert snapshot.total_checks == 3
    assert snapshot.successful_checks == 3
    assert snapshot.failed_checks == 0
    assert snapshot.avg_response_time_ms == pytest.approx(200.0)
    assert snapshot.min_response_time_ms == 100
    assert snapshot.max_response_time_ms == 300
    assert snapshot.uptime_percentage == pytest.approx(100.0)
    assert snapshot.check_pass_ratio == pytest.approx(100.0)
    assert snapshot.incidents_count == 0

    # Re-run after adding another check for the same day: upsert, not duplicate.
    await _insert_check(db_session, monitor_id, CheckStatus.SUCCESS, 400, period_start + timedelta(hours=4))
    await _aggregate_monitor_metrics(monitor_id, period_start, session=db_session)

    snapshots = await MetricSnapshotRepository(db_session).list_by_monitor(monitor_id, MetricPeriod.DAILY)
    assert len(snapshots) == 1
    assert snapshots[0].total_checks == 4
    assert snapshots[0].avg_response_time_ms == pytest.approx(250.0)


async def test_aggregate_daily_snapshot_unknown_monitor_raises_not_found(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await MetricsService(db_session).aggregate_daily_snapshot(uuid.uuid4(), _yesterday_utc_midnight())


async def test_dispatch_metric_aggregation_only_active_monitors(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await auth_headers(client, "metrics-owner10@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 10")
    active_monitor = await _create_monitor(client, headers, workspace["id"], target="https://active.example.com")
    inactive_monitor = await _create_monitor(
        client, headers, workspace["id"], target="https://inactive.example.com"
    )

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{inactive_monitor['id']}",
        json={"is_active": False},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    monitor_ids = await _get_aggregation_monitor_ids(session=db_session)

    assert uuid.UUID(active_monitor["id"]) in monitor_ids
    assert uuid.UUID(inactive_monitor["id"]) not in monitor_ids


# --- RBAC ---


async def test_non_member_cannot_view_latency_metrics(client: AsyncClient) -> None:
    headers = await auth_headers(client, "metrics-owner11@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 11")
    monitor = await _create_monitor(client, headers, workspace["id"])

    outsider_headers = await auth_headers(client, "metrics-outsider1@example.com")

    response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/metrics/latency", headers=outsider_headers
    )

    assert response.status_code == 403


async def test_non_member_cannot_view_dashboard(client: AsyncClient) -> None:
    headers = await auth_headers(client, "metrics-owner12@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 12")

    outsider_headers = await auth_headers(client, "metrics-outsider2@example.com")

    response = await client.get(f"/api/v1/workspaces/{workspace['id']}/dashboard", headers=outsider_headers)

    assert response.status_code == 403


async def test_latency_metrics_unknown_monitor_returns_404(client: AsyncClient) -> None:
    headers = await auth_headers(client, "metrics-owner13@example.com")
    workspace = await _create_workspace(client, headers, "Metrics Co 13")

    response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{uuid.uuid4()}/metrics/latency", headers=headers
    )

    assert response.status_code == 404
