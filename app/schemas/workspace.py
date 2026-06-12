import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import WorkspaceRole


class WorkspaceBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class WorkspaceCreate(WorkspaceBase):
    slug: str | None = Field(default=None, min_length=1, max_length=255)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class WorkspaceJoin(BaseModel):
    invite_code: str = Field(min_length=1, max_length=64)


class WorkspaceRead(WorkspaceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    # Only populated for the owner/admin of the workspace.
    invite_code: str | None = None
    # The requesting user's role in this workspace.
    role: WorkspaceRole
    created_at: datetime
    updated_at: datetime
