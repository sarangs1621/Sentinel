"""metric snapshots for analytics & reporting

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    metric_period = postgresql.ENUM("daily", name="metric_period")
    metric_period.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "metric_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monitor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "period_type",
            postgresql.ENUM("daily", name="metric_period", create_type=False),
            server_default="daily",
            nullable=False,
        ),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_checks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("successful_checks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_checks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("uptime_percentage", sa.Float(), nullable=True),
        sa.Column("check_pass_ratio", sa.Float(), nullable=True),
        sa.Column("avg_response_time_ms", sa.Float(), nullable=True),
        sa.Column("min_response_time_ms", sa.Integer(), nullable=True),
        sa.Column("max_response_time_ms", sa.Integer(), nullable=True),
        sa.Column("p95_response_time_ms", sa.Float(), nullable=True),
        sa.Column("incidents_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["monitor_id"], ["monitors.id"],
            name="fk_metric_snapshots_monitor_id_monitors", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_metric_snapshots_workspace_id_workspaces", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_metric_snapshots"),
        sa.UniqueConstraint(
            "monitor_id", "period_type", "period_start",
            name="uq_metric_snapshots_monitor_id_period_type_period_start",
        ),
    )
    op.create_index("ix_metric_snapshots_monitor_id", "metric_snapshots", ["monitor_id"])
    op.create_index("ix_metric_snapshots_workspace_id", "metric_snapshots", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_metric_snapshots_workspace_id", table_name="metric_snapshots")
    op.drop_index("ix_metric_snapshots_monitor_id", table_name="metric_snapshots")
    op.drop_table("metric_snapshots")

    metric_period = postgresql.ENUM("daily", name="metric_period")
    metric_period.drop(op.get_bind(), checkfirst=True)
