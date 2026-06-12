"""monitors and audit_logs

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    monitor_type = postgresql.ENUM("http", "tcp", "ping", name="monitor_type")
    monitor_type.create(op.get_bind(), checkfirst=True)

    monitor_status = postgresql.ENUM("pending", "up", "down", name="monitor_status")
    monitor_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "monitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "monitor_type",
            postgresql.ENUM("http", "tcp", "ping", name="monitor_type", create_type=False),
            nullable=False,
        ),
        sa.Column("target", sa.String(length=512), nullable=False),
        sa.Column("check_interval_seconds", sa.Integer(), server_default="60", nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("pending", "up", "down", name="monitor_status", create_type=False),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_monitors_workspace_id_workspaces", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name="fk_monitors_created_by_user_id_users", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_monitors"),
    )
    op.create_index("ix_monitors_workspace_id", "monitors", ["workspace_id"])
    op.create_index(
        "uq_monitors_workspace_id_monitor_type_target",
        "monitors",
        ["workspace_id", "monitor_type", "target"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_audit_logs_workspace_id_workspaces", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"],
            name="fk_audit_logs_actor_user_id_users", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_workspace_id", "audit_logs", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_workspace_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("uq_monitors_workspace_id_monitor_type_target", table_name="monitors")
    op.drop_index("ix_monitors_workspace_id", table_name="monitors")
    op.drop_table("monitors")

    monitor_status = postgresql.ENUM("pending", "up", "down", name="monitor_status")
    monitor_status.drop(op.get_bind(), checkfirst=True)

    monitor_type = postgresql.ENUM("http", "tcp", "ping", name="monitor_type")
    monitor_type.drop(op.get_bind(), checkfirst=True)
