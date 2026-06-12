import uuid
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends

from app.api.deps import DbSession, WorkspaceMembership
from app.schemas.metrics import (
    LatencyMetricsRead,
    MetricSnapshotRead,
    TimeRangeParams,
    UptimeReportRead,
    get_time_range,
)
from app.services.metrics import MetricsService

router = APIRouter()


@router.get("/latency", response_model=LatencyMetricsRead)
async def get_latency_metrics(
    monitor_id: uuid.UUID,
    membership: WorkspaceMembership,
    db: DbSession,
    time_range: Annotated[TimeRangeParams, Depends(get_time_range)],
) -> LatencyMetricsRead:
    workspace, _ = membership
    return await MetricsService(db).get_latency_metrics(
        workspace.id, monitor_id, cast(datetime, time_range.start), cast(datetime, time_range.end)
    )


@router.get("/uptime", response_model=UptimeReportRead)
async def get_uptime_report(
    monitor_id: uuid.UUID,
    membership: WorkspaceMembership,
    db: DbSession,
    time_range: Annotated[TimeRangeParams, Depends(get_time_range)],
) -> UptimeReportRead:
    workspace, _ = membership
    return await MetricsService(db).get_uptime_report(
        workspace.id, monitor_id, cast(datetime, time_range.start), cast(datetime, time_range.end)
    )


@router.get("/snapshots", response_model=list[MetricSnapshotRead])
async def list_snapshots(
    monitor_id: uuid.UUID,
    membership: WorkspaceMembership,
    db: DbSession,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[MetricSnapshotRead]:
    workspace, _ = membership
    return await MetricsService(db).list_snapshots(workspace.id, monitor_id, start, end)
