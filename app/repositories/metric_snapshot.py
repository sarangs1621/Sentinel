import uuid
from datetime import datetime

from sqlalchemy import select

from app.models.enums import MetricPeriod
from app.models.metric_snapshot import MetricSnapshot
from app.repositories.base import BaseRepository


class MetricSnapshotRepository(BaseRepository[MetricSnapshot]):
    model = MetricSnapshot

    async def get_by_monitor_period(
        self, monitor_id: uuid.UUID, period_type: MetricPeriod, period_start: datetime
    ) -> MetricSnapshot | None:
        result = await self.session.execute(
            select(MetricSnapshot).where(
                MetricSnapshot.monitor_id == monitor_id,
                MetricSnapshot.period_type == period_type,
                MetricSnapshot.period_start == period_start,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_monitor(
        self,
        monitor_id: uuid.UUID,
        period_type: MetricPeriod = MetricPeriod.DAILY,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[MetricSnapshot]:
        query = select(MetricSnapshot).where(
            MetricSnapshot.monitor_id == monitor_id,
            MetricSnapshot.period_type == period_type,
        )
        if start is not None:
            query = query.where(MetricSnapshot.period_start >= start)
        if end is not None:
            query = query.where(MetricSnapshot.period_start < end)
        query = query.order_by(MetricSnapshot.period_start)
        result = await self.session.execute(query)
        return list(result.scalars().all())
