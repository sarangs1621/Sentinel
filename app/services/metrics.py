import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.enums import CheckStatus, IncidentStatus, MetricPeriod, MonitorStatus
from app.models.incident import Incident
from app.models.metric_snapshot import MetricSnapshot
from app.models.monitor import Monitor
from app.repositories.check import CheckRepository
from app.repositories.incident import IncidentRepository
from app.repositories.metric_snapshot import MetricSnapshotRepository
from app.repositories.monitor import MonitorRepository
from app.schemas.metrics import (
    IncidentStatusCounts,
    LatencyMetricsRead,
    MetricSnapshotRead,
    MonitorStatusCounts,
    UptimeReportRead,
    WorkspaceDashboardRead,
)
from app.services.cache import CacheService

DASHBOARD_WINDOW = timedelta(hours=24)


class MetricsService:
    def __init__(self, session: AsyncSession, cache: CacheService | None = None) -> None:
        self.session = session
        self.checks = CheckRepository(session)
        self.incidents = IncidentRepository(session)
        self.monitors = MonitorRepository(session)
        self.snapshots = MetricSnapshotRepository(session)
        self.cache = cache if cache is not None else CacheService()

    @staticmethod
    def to_snapshot_read(snapshot: MetricSnapshot) -> MetricSnapshotRead:
        return MetricSnapshotRead.model_validate(snapshot)

    async def _get_active_monitor(self, workspace_id: uuid.UUID, monitor_id: uuid.UUID) -> Monitor:
        monitor = await self.monitors.get_active_by_id(workspace_id, monitor_id)
        if monitor is None:
            raise NotFoundError("Monitor not found.")
        return monitor

    @staticmethod
    def _compute_downtime(incidents: list[Incident], start: datetime, end: datetime) -> timedelta:
        """Sum the overlap of each incident's `[created_at, resolved_at or now)`
        window with `[start, end)`.

        Relies on the codebase invariant (CheckService._open_incident_if_needed /
        IncidentRepository.get_open_for_monitor) that a monitor has at most one
        open incident at a time, so per-monitor incident windows never overlap
        each other and a simple sum is correct.
        """
        now = datetime.now(UTC)
        total = timedelta(0)
        for incident in incidents:
            overlap_start = max(incident.created_at, start)
            overlap_end = min(incident.resolved_at or now, end)
            if overlap_end > overlap_start:
                total += overlap_end - overlap_start
        return total

    # ------------------------------------------------------------------
    async def get_latency_metrics(
        self, workspace_id: uuid.UUID, monitor_id: uuid.UUID, start: datetime, end: datetime
    ) -> LatencyMetricsRead:
        await self._get_active_monitor(workspace_id, monitor_id)

        params = f"{start.isoformat()}:{end.isoformat()}"
        cached = await self.cache.get_analytics("latency", monitor_id, params)
        if cached is not None:
            return LatencyMetricsRead.model_validate(cached)

        row = await self.checks.get_latency_stats(monitor_id, start, end)

        result = LatencyMetricsRead(
            monitor_id=monitor_id,
            period_start=start,
            period_end=end,
            total_checks=row._mapping["count"] or 0,
            avg_response_time_ms=float(row.avg) if row.avg is not None else None,
            min_response_time_ms=row.min,
            max_response_time_ms=row.max,
            p50_response_time_ms=float(row.p50) if row.p50 is not None else None,
            p95_response_time_ms=float(row.p95) if row.p95 is not None else None,
            p99_response_time_ms=float(row.p99) if row.p99 is not None else None,
        )
        await self.cache.set_analytics("latency", monitor_id, params, result.model_dump(mode="json"))
        return result

    # ------------------------------------------------------------------
    async def get_uptime_report(
        self, workspace_id: uuid.UUID, monitor_id: uuid.UUID, start: datetime, end: datetime
    ) -> UptimeReportRead:
        await self._get_active_monitor(workspace_id, monitor_id)

        params = f"{start.isoformat()}:{end.isoformat()}"
        cached = await self.cache.get_analytics("uptime", monitor_id, params)
        if cached is not None:
            return UptimeReportRead.model_validate(cached)

        status_counts = await self.checks.count_by_status(monitor_id, start, end)
        successful = status_counts.get(CheckStatus.SUCCESS, 0)
        failed = status_counts.get(CheckStatus.FAILURE, 0)
        total = successful + failed
        check_pass_ratio = (successful / total * 100) if total > 0 else None

        incidents = await self.incidents.list_overlapping(monitor_id, start, end)
        total_downtime = self._compute_downtime(incidents, start, end)

        period_duration = (end - start).total_seconds()
        uptime_percentage = max(
            0.0, min(100.0, (period_duration - total_downtime.total_seconds()) / period_duration * 100)
        )

        result = UptimeReportRead(
            monitor_id=monitor_id,
            period_start=start,
            period_end=end,
            total_checks=total,
            successful_checks=successful,
            failed_checks=failed,
            check_pass_ratio=check_pass_ratio,
            uptime_percentage=uptime_percentage,
            total_downtime_seconds=total_downtime.total_seconds(),
            incidents_count=len(incidents),
        )
        await self.cache.set_analytics("uptime", monitor_id, params, result.model_dump(mode="json"))
        return result

    # ------------------------------------------------------------------
    async def list_snapshots(
        self,
        workspace_id: uuid.UUID,
        monitor_id: uuid.UUID,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[MetricSnapshotRead]:
        await self._get_active_monitor(workspace_id, monitor_id)

        params = f"{start.isoformat() if start else 'none'}:{end.isoformat() if end else 'none'}"
        cached = await self.cache.get_analytics("snapshots", monitor_id, params)
        if cached is not None:
            return [MetricSnapshotRead.model_validate(item) for item in cached]

        snapshots = await self.snapshots.list_by_monitor(monitor_id, MetricPeriod.DAILY, start, end)
        result = [self.to_snapshot_read(s) for s in snapshots]
        await self.cache.set_analytics(
            "snapshots", monitor_id, params, [s.model_dump(mode="json") for s in result]
        )
        return result

    # ------------------------------------------------------------------
    async def get_workspace_dashboard(self, workspace_id: uuid.UUID) -> WorkspaceDashboardRead:
        cached = await self.cache.get_dashboard(workspace_id)
        if cached is not None:
            return WorkspaceDashboardRead.model_validate(cached)

        end = datetime.now(UTC)
        start = end - DASHBOARD_WINDOW

        monitor_counts = await self.monitors.count_by_workspace_status(workspace_id)
        incident_counts = await self.incidents.count_by_workspace_status(workspace_id)
        monitors = await self.monitors.list_by_workspace(workspace_id)

        total_checks = 0
        total_successful = 0
        weighted_avg_sum = 0.0
        weighted_avg_count = 0

        for monitor in monitors:
            status_counts = await self.checks.count_by_status(monitor.id, start, end)
            successful = status_counts.get(CheckStatus.SUCCESS, 0)
            failed = status_counts.get(CheckStatus.FAILURE, 0)
            total_checks += successful + failed
            total_successful += successful

            row = await self.checks.get_latency_stats(monitor.id, start, end)
            row_count = row._mapping["count"]
            if row.avg is not None and row_count:
                weighted_avg_sum += float(row.avg) * row_count
                weighted_avg_count += row_count

        overall_pass_ratio = (total_successful / total_checks * 100) if total_checks > 0 else None
        avg_response = (weighted_avg_sum / weighted_avg_count) if weighted_avg_count > 0 else None

        result = WorkspaceDashboardRead(
            workspace_id=workspace_id,
            period_start=start,
            period_end=end,
            total_monitors=len(monitors),
            monitor_status_counts=MonitorStatusCounts(
                pending=monitor_counts.get(MonitorStatus.PENDING, 0),
                up=monitor_counts.get(MonitorStatus.UP, 0),
                down=monitor_counts.get(MonitorStatus.DOWN, 0),
            ),
            incident_status_counts=IncidentStatusCounts(
                open=incident_counts.get(IncidentStatus.OPEN, 0),
                investigating=incident_counts.get(IncidentStatus.INVESTIGATING, 0),
                resolved=incident_counts.get(IncidentStatus.RESOLVED, 0),
            ),
            total_checks=total_checks,
            overall_check_pass_ratio=overall_pass_ratio,
            avg_response_time_ms=avg_response,
        )
        await self.cache.set_dashboard(workspace_id, result.model_dump(mode="json"))
        return result

    # ------------------------------------------------------------------
    # Aggregation (used by the Celery aggregation task)
    # ------------------------------------------------------------------
    async def aggregate_daily_snapshot(self, monitor_id: uuid.UUID, period_start: datetime) -> MetricSnapshot:
        """Compute and upsert the `MetricSnapshot` for the UTC day starting at
        `period_start` (must be midnight UTC). Idempotent: re-running for the
        same monitor/day updates the existing row rather than duplicating."""
        monitor = await self.monitors.get_by_id(monitor_id)
        if monitor is None:
            raise NotFoundError("Monitor not found.")

        period_end = period_start + timedelta(days=1)

        status_counts = await self.checks.count_by_status(monitor_id, period_start, period_end)
        successful = status_counts.get(CheckStatus.SUCCESS, 0)
        failed = status_counts.get(CheckStatus.FAILURE, 0)
        total = successful + failed
        check_pass_ratio = (successful / total * 100) if total > 0 else None

        latency_row = await self.checks.get_latency_stats(monitor_id, period_start, period_end)

        incidents = await self.incidents.list_overlapping(monitor_id, period_start, period_end)
        total_downtime = self._compute_downtime(incidents, period_start, period_end)

        period_duration = (period_end - period_start).total_seconds()
        uptime_percentage = max(
            0.0, min(100.0, (period_duration - total_downtime.total_seconds()) / period_duration * 100)
        )

        existing = await self.snapshots.get_by_monitor_period(monitor_id, MetricPeriod.DAILY, period_start)
        if existing is None:
            snapshot = MetricSnapshot(
                monitor_id=monitor_id,
                workspace_id=monitor.workspace_id,
                period_type=MetricPeriod.DAILY,
                period_start=period_start,
                period_end=period_end,
            )
            self.snapshots.add(snapshot)
        else:
            snapshot = existing

        snapshot.total_checks = total
        snapshot.successful_checks = successful
        snapshot.failed_checks = failed
        snapshot.uptime_percentage = uptime_percentage
        snapshot.check_pass_ratio = check_pass_ratio
        snapshot.avg_response_time_ms = float(latency_row.avg) if latency_row.avg is not None else None
        snapshot.min_response_time_ms = latency_row.min
        snapshot.max_response_time_ms = latency_row.max
        snapshot.p95_response_time_ms = float(latency_row.p95) if latency_row.p95 is not None else None
        snapshot.incidents_count = len(incidents)

        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(snapshot)
        await self.cache.invalidate_analytics(monitor_id)
        return snapshot
