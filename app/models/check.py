import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import CheckStatus, enum_column_values
from app.models.mixins import CreatedAtMixin, UUIDPkMixin


class Check(UUIDPkMixin, CreatedAtMixin, Base):
    """A single health check result for a monitor."""

    __tablename__ = "checks"
    __table_args__ = (
        Index("ix_checks_created_at", "created_at"),
        Index("ix_checks_monitor_id_created_at", "monitor_id", "created_at"),
        Index("ix_checks_monitor_id_status_created_at", "monitor_id", "status", "created_at"),
    )

    monitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("monitors.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[CheckStatus] = mapped_column(
        SAEnum(
            CheckStatus,
            name="check_status",
            native_enum=True,
            validate_strings=True,
            values_callable=enum_column_values,
        ),
        nullable=False,
    )
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    def __repr__(self) -> str:
        return f"<Check id={self.id} monitor_id={self.monitor_id} status={self.status}>"
