import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import WorkspaceRole


class WorkspaceMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    email: str
    full_name: str | None
    role: WorkspaceRole
    created_at: datetime  # joined_at


class WorkspaceMemberRoleUpdate(BaseModel):
    role: WorkspaceRole
