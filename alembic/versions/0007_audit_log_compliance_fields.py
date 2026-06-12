"""audit log compliance fields

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("audit_logs", "actor_user_id", new_column_name="user_id")
    op.alter_column("audit_logs", "resource_type", new_column_name="entity_type")
    op.alter_column("audit_logs", "resource_id", new_column_name="entity_id")
    op.alter_column("audit_logs", "details", new_column_name="new_values")

    op.add_column("audit_logs", sa.Column("old_values", postgresql.JSONB(), nullable=True))
    op.add_column("audit_logs", sa.Column("ip_address", sa.String(length=45), nullable=True))
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(length=512), nullable=True))

    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")

    op.drop_column("audit_logs", "user_agent")
    op.drop_column("audit_logs", "ip_address")
    op.drop_column("audit_logs", "old_values")

    op.alter_column("audit_logs", "new_values", new_column_name="details")
    op.alter_column("audit_logs", "entity_id", new_column_name="resource_id")
    op.alter_column("audit_logs", "entity_type", new_column_name="resource_type")
    op.alter_column("audit_logs", "user_id", new_column_name="actor_user_id")
