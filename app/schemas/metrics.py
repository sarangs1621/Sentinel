import uuid
from datetime import UTC, datetime, timedelta

from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.models.enums import MetricPeriod

DEFAULT_WINDOW = timedelta(hours=24)
MAX_RANGE = timedelta(days=90)


class TimeRangeParams(BaseModel):
    """Shared start/end query-param validation for latency & uptime endpoints.

    Defaults to the trailing 24 hours if either bound is omitted. Requires
    `end` to be after `start` and caps the range at 90 days.
    """

    start: datetime | None = None
    end: datetime | None = None

    @model_validator(mode="after")
    def _apply_defaults_and_validate(self) -> "TimeRangeParams":
        now = datetime.now(UTC)
        end = self.end or now
        start = self.start or (end - DEFAULT_WINDOW)

        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)

        if end <= start:
            raise ValueError("end must be after start")
        if end - start > MAX_RANGE:
            raise ValueError("time range cannot exceed 90 days")

        self.start = start
        self.end = end
        return self


def get_time_range(start: datetime | None = None, end: datetime | None = None) -> TimeRangeParams:
    """FastAPI dependency wrapping `TimeRangeParams`.

    `Depends()`-on-a-model calls `TimeRangeParams(**params)` directly, and a
    `pydantic.ValidationError` raised there (e.g. from the `model_validator`)
    isn't caught by FastAPI's request-validation error handling and would
    surface as a 500. Catching it here and re-raising as
    `RequestValidationError` restores the normal 422 response.
    """
    try:
        return TimeRangeParams(start=start, end=end)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


class LatencyMetricsRead(BaseModel):
    monitor_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    total_checks: int
    avg_response_time_ms: float | None
    min_response_time_ms: int | None
    max_response_time_ms: int | None
    p50_response_time_ms: float | None
    p95_response_time_ms: float | None
    p99_response_time_ms: float | None


class UptimeReportRead(BaseModel):
    monitor_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    total_checks: int
    successful_checks: int
    failed_checks: int
    check_pass_ratio: float | None
    uptime_percentage: float
    total_downtime_seconds: float
    incidents_count: int


class MetricSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    monitor_id: uuid.UUID
    workspace_id: uuid.UUID
    period_type: MetricPeriod
    period_start: datetime
    period_end: datetime
    total_checks: int
    successful_checks: int
    failed_checks: int
    uptime_percentage: float | None
    check_pass_ratio: float | None
    avg_response_time_ms: float | None
    min_response_time_ms: int | None
    max_response_time_ms: int | None
    p95_response_time_ms: float | None
    incidents_count: int
    created_at: datetime


class MonitorStatusCounts(BaseModel):
    pending: int = 0
    up: int = 0
    down: int = 0


class IncidentStatusCounts(BaseModel):
    open: int = 0
    investigating: int = 0
    resolved: int = 0


class WorkspaceDashboardRead(BaseModel):
    workspace_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    total_monitors: int
    monitor_status_counts: MonitorStatusCounts
    incident_status_counts: IncidentStatusCounts
    total_checks: int
    overall_check_pass_ratio: float | None
    avg_response_time_ms: float | None
