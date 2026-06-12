"""alert rules (replaces alert channels) and email notifications

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    notification_channel = postgresql.ENUM("webhook", "email", name="notification_channel")
    notification_channel.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "channel_type",
            postgresql.ENUM("webhook", "email", name="notification_channel", create_type=False),
            nullable=False,
        ),
        sa.Column("target", sa.String(length=2048), nullable=False),
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
            name="fk_alert_rules_workspace_id_workspaces", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_alert_rules"),
    )
    op.create_index("ix_alert_rules_workspace_id", "alert_rules", ["workspace_id"])

    # Notifications used to reference the workspace's single alert_channel
    # implicitly; that model is replaced by per-rule alert_rule_id, so any
    # existing (pre-refactor) notification rows can't be backfilled.
    op.execute("DELETE FROM notifications")
    op.add_column("notifications", sa.Column("alert_rule_id", postgresql.UUID(as_uuid=True), nullable=False))
    op.create_foreign_key(
        "fk_notifications_alert_rule_id_alert_rules",
        "notifications", "alert_rules", ["alert_rule_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_notifications_alert_rule_id", "notifications", ["alert_rule_id"])

    op.drop_table("alert_channels")


def downgrade() -> None:
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

    op.execute("DELETE FROM notifications")
    op.drop_index("ix_notifications_alert_rule_id", table_name="notifications")
    op.drop_constraint("fk_notifications_alert_rule_id_alert_rules", "notifications", type_="foreignkey")
    op.drop_column("notifications", "alert_rule_id")

    op.drop_index("ix_alert_rules_workspace_id", table_name="alert_rules")
    op.drop_table("alert_rules")

    notification_channel = postgresql.ENUM("webhook", "email", name="notification_channel")
    notification_channel.drop(op.get_bind(), checkfirst=True)
