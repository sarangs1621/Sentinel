"""alert channels and notifications

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    notification_event = postgresql.ENUM("incident_opened", "incident_resolved", name="notification_event")
    notification_event.create(op.get_bind(), checkfirst=True)

    notification_status = postgresql.ENUM("pending", "sent", "failed", name="notification_status")
    notification_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "alert_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("webhook_url", sa.String(length=2048), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "min_severity",
            postgresql.ENUM("critical", "major", "minor", name="incident_severity", create_type=False),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_alert_channels_workspace_id_workspaces", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_alert_channels"),
        sa.UniqueConstraint("workspace_id", name="uq_alert_channels_workspace_id"),
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "event_type",
            postgresql.ENUM("incident_opened", "incident_resolved", name="notification_event", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM("pending", "sent", "failed", name="notification_status", create_type=False),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_notifications_workspace_id_workspaces", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.id"],
            name="fk_notifications_incident_id_incidents", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
    )
    op.create_index("ix_notifications_workspace_id", "notifications", ["workspace_id"])
    op.create_index("ix_notifications_incident_id", "notifications", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_incident_id", table_name="notifications")
    op.drop_index("ix_notifications_workspace_id", table_name="notifications")
    op.drop_table("notifications")

    op.drop_table("alert_channels")

    notification_status = postgresql.ENUM("pending", "sent", "failed", name="notification_status")
    notification_status.drop(op.get_bind(), checkfirst=True)

    notification_event = postgresql.ENUM("incident_opened", "incident_resolved", name="notification_event")
    notification_event.drop(op.get_bind(), checkfirst=True)
