"""checks, incidents, and monitor failure-tracking fields

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    check_status = postgresql.ENUM("success", "failure", name="check_status")
    check_status.create(op.get_bind(), checkfirst=True)

    incident_status = postgresql.ENUM("open", "investigating", "resolved", name="incident_status")
    incident_status.create(op.get_bind(), checkfirst=True)

    incident_severity = postgresql.ENUM("critical", "major", "minor", name="incident_severity")
    incident_severity.create(op.get_bind(), checkfirst=True)

    op.add_column("monitors", sa.Column("failure_threshold", sa.Integer(), server_default="3", nullable=False))
    op.add_column("monitors", sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False))
    op.add_column("monitors", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monitor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("success", "failure", name="check_status", create_type=False),
            nullable=False,
        ),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["monitor_id"], ["monitors.id"],
            name="fk_checks_monitor_id_monitors", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_checks"),
    )
    op.create_index("ix_checks_monitor_id", "checks", ["monitor_id"])

    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monitor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("open", "investigating", "resolved", name="incident_status", create_type=False),
            server_default="open",
            nullable=False,
        ),
        sa.Column(
            "severity",
            postgresql.ENUM("critical", "major", "minor", name="incident_severity", create_type=False),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_incidents_workspace_id_workspaces", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["monitor_id"], ["monitors.id"],
            name="fk_incidents_monitor_id_monitors", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_incidents"),
    )
    op.create_index("ix_incidents_workspace_id", "incidents", ["workspace_id"])
    op.create_index("ix_incidents_monitor_id", "incidents", ["monitor_id"])


def downgrade() -> None:
    op.drop_index("ix_incidents_monitor_id", table_name="incidents")
    op.drop_index("ix_incidents_workspace_id", table_name="incidents")
    op.drop_table("incidents")

    op.drop_index("ix_checks_monitor_id", table_name="checks")
    op.drop_table("checks")

    op.drop_column("monitors", "last_checked_at")
    op.drop_column("monitors", "consecutive_failures")
    op.drop_column("monitors", "failure_threshold")

    incident_severity = postgresql.ENUM("critical", "major", "minor", name="incident_severity")
    incident_severity.drop(op.get_bind(), checkfirst=True)

    incident_status = postgresql.ENUM("open", "investigating", "resolved", name="incident_status")
    incident_status.drop(op.get_bind(), checkfirst=True)

    check_status = postgresql.ENUM("success", "failure", name="check_status")
    check_status.drop(op.get_bind(), checkfirst=True)
