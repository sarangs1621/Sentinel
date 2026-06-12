import uuid

from sqlalchemy import Boolean, ForeignKey, String, true
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import IncidentSeverity, NotificationChannel, enum_column_values
from app.models.mixins import TimestampMixin, UUIDPkMixin


class AlertRule(UUIDPkMixin, TimestampMixin, Base):
    """A workspace's notification rule: where to send incident alerts and which to send."""

    __tablename__ = "alert_rules"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_type: Mapped[NotificationChannel] = mapped_column(
        SAEnum(
            NotificationChannel,
            name="notification_channel",
            native_enum=True,
            validate_strings=True,
            values_callable=enum_column_values,
        ),
        nullable=False,
    )
    target: Mapped[str] = mapped_column(String(2048), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    min_severity: Mapped[IncidentSeverity | None] = mapped_column(
        SAEnum(
            IncidentSeverity,
            name="incident_severity",
            native_enum=True,
            validate_strings=True,
            values_callable=enum_column_values,
        ),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<AlertRule id={self.id} workspace_id={self.workspace_id} channel_type={self.channel_type}>"
