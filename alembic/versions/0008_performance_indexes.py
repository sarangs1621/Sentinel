"""performance indexes for monitors, checks, incidents, notifications

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_monitors_is_active", "monitors", ["is_active"])
    op.create_index("ix_monitors_deleted_at", "monitors", ["deleted_at"])

    op.create_index("ix_checks_created_at", "checks", ["created_at"])
    op.create_index("ix_checks_monitor_id_created_at", "checks", ["monitor_id", "created_at"])
    op.create_index("ix_checks_monitor_id_status_created_at", "checks", ["monitor_id", "status", "created_at"])

    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_created_at", "incidents", ["created_at"])

    op.create_index("ix_notifications_status", "notifications", ["status"])


def downgrade() -> None:
    op.drop_index("ix_notifications_status", table_name="notifications")

    op.drop_index("ix_incidents_created_at", table_name="incidents")
    op.drop_index("ix_incidents_status", table_name="incidents")

    op.drop_index("ix_checks_monitor_id_status_created_at", table_name="checks")
    op.drop_index("ix_checks_monitor_id_created_at", table_name="checks")
    op.drop_index("ix_checks_created_at", table_name="checks")

    op.drop_index("ix_monitors_deleted_at", table_name="monitors")
    op.drop_index("ix_monitors_is_active", table_name="monitors")
