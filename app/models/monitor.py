import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, text, true
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MonitorStatus, MonitorType, enum_column_values
from app.models.mixins import TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.workspace import Workspace


class Monitor(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "monitors"
    __table_args__ = (
        Index(
            "uq_monitors_workspace_id_monitor_type_target",
            "workspace_id",
            "monitor_type",
            "target",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_monitors_is_active", "is_active"),
        Index("ix_monitors_deleted_at", "deleted_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    monitor_type: Mapped[MonitorType] = mapped_column(
        SAEnum(
            MonitorType,
            name="monitor_type",
            native_enum=True,
            validate_strings=True,
            values_callable=enum_column_values,
        ),
        nullable=False,
    )
    target: Mapped[str] = mapped_column(String(512), nullable=False)
    check_interval_seconds: Mapped[int] = mapped_column(Integer, default=60, server_default="60", nullable=False)
    failure_threshold: Mapped[int] = mapped_column(Integer, default=3, server_default="3", nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[MonitorStatus] = mapped_column(
        SAEnum(
            MonitorStatus,
            name="monitor_status",
            native_enum=True,
            validate_strings=True,
            values_callable=enum_column_values,
        ),
        default=MonitorStatus.PENDING,
        server_default=MonitorStatus.PENDING.value,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped["Workspace"] = relationship(back_populates="monitors")
    created_by: Mapped["User | None"] = relationship()

    def __repr__(self) -> str:
        return f"<Monitor id={self.id} workspace_id={self.workspace_id} target={self.target!r}>"
