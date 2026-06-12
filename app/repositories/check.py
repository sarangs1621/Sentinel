import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.engine import Row

from app.models.check import Check
from app.models.enums import CheckStatus
from app.repositories.base import BaseRepository


class CheckRepository(BaseRepository[Check]):
    model = Check

    async def list_by_monitor(self, monitor_id: uuid.UUID) -> list[Check]:
        result = await self.session.execute(
            select(Check).where(Check.monitor_id == monitor_id).order_by(Check.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_latency_stats(self, monitor_id: uuid.UUID, start: datetime, end: datetime) -> Row:
        """Count, avg/min/max, and p50/p95/p99 of `response_time_ms` for checks
        in [start, end). All stats are `None` (and count is 0) if there are no
        checks with a non-null `response_time_ms` in range."""
        result = await self.session.execute(
            select(
                func.count(Check.response_time_ms).label("count"),
                func.avg(Check.response_time_ms).label("avg"),
                func.min(Check.response_time_ms).label("min"),
                func.max(Check.response_time_ms).label("max"),
                func.percentile_cont(0.5).within_group(Check.response_time_ms.asc()).label("p50"),
                func.percentile_cont(0.95).within_group(Check.response_time_ms.asc()).label("p95"),
                func.percentile_cont(0.99).within_group(Check.response_time_ms.asc()).label("p99"),
            ).where(
                Check.monitor_id == monitor_id,
                Check.created_at >= start,
                Check.created_at < end,
                Check.response_time_ms.is_not(None),
            )
        )
        return result.one()

    async def count_by_status(self, monitor_id: uuid.UUID, start: datetime, end: datetime) -> dict[CheckStatus, int]:
        """Counts of checks grouped by status for checks in [start, end)."""
        result = await self.session.execute(
            select(Check.status, func.count())
            .where(Check.monitor_id == monitor_id, Check.created_at >= start, Check.created_at < end)
            .group_by(Check.status)
        )
        return {status: count for status, count in result.all()}
