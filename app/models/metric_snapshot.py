import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import MetricPeriod, enum_column_values
from app.models.mixins import CreatedAtMixin, UUIDPkMixin


class MetricSnapshot(UUIDPkMixin, CreatedAtMixin, Base):
    """A persisted, periodic aggregate of a monitor's checks and incidents."""

    __tablename__ = "metric_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "monitor_id", "period_type", "period_start",
            name="uq_metric_snapshots_monitor_id_period_type_period_start",
        ),
    )

    monitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monitors.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    period_type: Mapped[MetricPeriod] = mapped_column(
        SAEnum(
            MetricPeriod, name="metric_period", native_enum=True,
            validate_strings=True, values_callable=enum_column_values,
        ),
        default=MetricPeriod.DAILY, server_default=MetricPeriod.DAILY.value, nullable=False,
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    total_checks: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    successful_checks: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    failed_checks: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    uptime_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    check_pass_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    avg_response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    p95_response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    incidents_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    def __repr__(self) -> str:
        return (
            f"<MetricSnapshot monitor_id={self.monitor_id} period_type={self.period_type} "
            f"period_start={self.period_start}>"
        )
