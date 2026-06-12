import re
import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.models.enums import WorkspaceRole
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.repositories.workspace import WorkspaceRepository
from app.repositories.workspace_member import WorkspaceMemberRepository
from app.schemas.workspace import WorkspaceCreate, WorkspaceJoin, WorkspaceRead, WorkspaceUpdate
from app.schemas.workspace_member import WorkspaceMemberRead, WorkspaceMemberRoleUpdate
from app.services.audit_log import AuditLogService, to_jsonable

_SLUG_INVALID_CHARS = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    slug = _SLUG_INVALID_CHARS.sub("-", text.lower()).strip("-")
    return slug[:255] or "workspace"


def _generate_invite_code() -> str:
    return secrets.token_urlsafe(12)


class WorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.workspaces = WorkspaceRepository(session)
        self.members = WorkspaceMemberRepository(session)
        self.audit = AuditLogService(session)

    # ------------------------------------------------------------------
    # Read-model helpers (also used directly by endpoints that already
    # hold ORM objects from a dependency, to avoid redundant queries)
    # ------------------------------------------------------------------
    @staticmethod
    def to_workspace_read(workspace: Workspace, member: WorkspaceMember) -> WorkspaceRead:
        is_privileged = member.role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)
        return WorkspaceRead(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            description=workspace.description,
            invite_code=workspace.invite_code if is_privileged else None,
            role=member.role,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )

    @staticmethod
    def to_member_read(member: WorkspaceMember) -> WorkspaceMemberRead:
        return WorkspaceMemberRead(
            user_id=member.user_id,
            email=member.user.email,
            full_name=member.user.full_name,
            role=member.role,
            created_at=member.created_at,
        )

    async def _generate_unique_slug(self, text: str) -> str:
        base = _slugify(text)
        slug = base
        while await self.workspaces.slug_exists(slug):
            slug = f"{base}-{secrets.token_hex(3)}"
        return slug

    # ------------------------------------------------------------------
    # Membership lookup (used by API dependencies for auth checks)
    # ------------------------------------------------------------------
    async def get_workspace_and_membership(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[Workspace, WorkspaceMember]:
        workspace = await self.workspaces.get_by_id(workspace_id)
        if workspace is None:
            raise NotFoundError("Workspace not found.")

        member = await self.members.get_by_workspace_and_user(workspace_id, user_id)
        if member is None:
            raise PermissionDeniedError("You are not a member of this workspace.")

        return workspace, member

    # ------------------------------------------------------------------
    # Use cases
    # ------------------------------------------------------------------
    async def create_workspace(self, user: User, data: WorkspaceCreate) -> WorkspaceRead:
        slug = await self._generate_unique_slug(data.slug or data.name)

        workspace = Workspace(
            name=data.name,
            slug=slug,
            description=data.description,
            invite_code=_generate_invite_code(),
        )
        self.workspaces.add(workspace)
        await self.session.flush()

        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
        )
        self.members.add(member)

        await self.session.commit()
        await self.session.refresh(workspace)

        return self.to_workspace_read(workspace, member)

    async def list_workspaces(self, user: User) -> list[WorkspaceRead]:
        memberships = await self.members.list_by_user(user.id)
        return [self.to_workspace_read(m.workspace, m) for m in memberships]

    async def join_workspace(
        self, user: User, data: WorkspaceJoin, ip_address: str | None = None, user_agent: str | None = None
    ) -> WorkspaceRead:
        workspace = await self.workspaces.get_by_invite_code(data.invite_code)
        if workspace is None:
            raise NotFoundError("Invalid invite code.")

        existing = await self.members.get_by_workspace_and_user(workspace.id, user.id)
        if existing is not None:
            raise ConflictError("You are already a member of this workspace.")

        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.MEMBER,
        )
        self.members.add(member)
        await self.session.flush()

        await self.audit.record(
            workspace.id,
            user.id,
            "member.added",
            "user",
            user.id,
            None,
            {"role": to_jsonable(member.role)},
            ip_address,
            user_agent,
        )

        await self.session.commit()

        return self.to_workspace_read(workspace, member)

    async def update_workspace(
        self,
        workspace_id: uuid.UUID,
        data: WorkspaceUpdate,
        member: WorkspaceMember,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> WorkspaceRead:
        workspace = await self.workspaces.get_by_id(workspace_id)
        if workspace is None:
            raise NotFoundError("Workspace not found.")

        updates = data.model_dump(exclude_unset=True)
        old_values = {field: to_jsonable(getattr(workspace, field)) for field in updates}

        for field, value in updates.items():
            setattr(workspace, field, value)

        new_values = {field: to_jsonable(getattr(workspace, field)) for field in updates}

        await self.audit.record(
            workspace_id,
            member.user_id,
            "workspace.updated",
            "workspace",
            workspace_id,
            old_values,
            new_values,
            ip_address,
            user_agent,
        )

        await self.session.commit()
        await self.session.refresh(workspace)
        return self.to_workspace_read(workspace, member)

    async def delete_workspace(self, workspace_id: uuid.UUID) -> None:
        workspace = await self.workspaces.get_by_id(workspace_id)
        if workspace is None:
            raise NotFoundError("Workspace not found.")

        await self.workspaces.delete(workspace)
        await self.session.commit()

    async def regenerate_invite_code(
        self, workspace_id: uuid.UUID, member: WorkspaceMember
    ) -> WorkspaceRead:
        workspace = await self.workspaces.get_by_id(workspace_id)
        if workspace is None:
            raise NotFoundError("Workspace not found.")

        workspace.invite_code = _generate_invite_code()
        await self.session.commit()
        await self.session.refresh(workspace)
        return self.to_workspace_read(workspace, member)

    async def list_members(self, workspace_id: uuid.UUID) -> list[WorkspaceMemberRead]:
        members = await self.members.list_by_workspace(workspace_id)
        return [self.to_member_read(m) for m in members]

    async def update_member_role(
        self,
        workspace_id: uuid.UUID,
        target_user_id: uuid.UUID,
        data: WorkspaceMemberRoleUpdate,
        acting_member: WorkspaceMember,
    ) -> WorkspaceMemberRead:
        target = await self.members.get_by_workspace_and_user(workspace_id, target_user_id)
        if target is None:
            raise NotFoundError("Member not found.")

        involves_owner_role = WorkspaceRole.OWNER in (target.role, data.role)
        if involves_owner_role and acting_member.role != WorkspaceRole.OWNER:
            raise PermissionDeniedError("Only an owner can grant or revoke the owner role.")

        if target.role == WorkspaceRole.OWNER and data.role != WorkspaceRole.OWNER:
            owner_count = await self.members.count_by_workspace_and_role(workspace_id, WorkspaceRole.OWNER)
            if owner_count <= 1:
                raise ConflictError("Cannot demote the only owner of the workspace.")

        target.role = data.role
        await self.session.commit()
        await self.session.refresh(target)
        return self.to_member_read(target)

    async def remove_member(
        self,
        workspace_id: uuid.UUID,
        target_user_id: uuid.UUID,
        acting_member: WorkspaceMember,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        target = await self.members.get_by_workspace_and_user(workspace_id, target_user_id)
        if target is None:
            raise NotFoundError("Member not found.")

        if target.role == WorkspaceRole.OWNER:
            if acting_member.role != WorkspaceRole.OWNER:
                raise PermissionDeniedError("Only an owner can remove an owner.")
            owner_count = await self.members.count_by_workspace_and_role(workspace_id, WorkspaceRole.OWNER)
            if owner_count <= 1:
                raise ConflictError("Cannot remove the only owner of the workspace.")

        old_role = to_jsonable(target.role)
        await self.members.delete(target)

        await self.audit.record(
            workspace_id,
            acting_member.user_id,
            "member.removed",
            "user",
            target_user_id,
            {"role": old_role},
            None,
            ip_address,
            user_agent,
        )

        await self.session.commit()

    async def leave_workspace(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, ip_address: str | None = None, user_agent: str | None = None
    ) -> None:
        member = await self.members.get_by_workspace_and_user(workspace_id, user_id)
        if member is None:
            raise NotFoundError("You are not a member of this workspace.")

        if member.role == WorkspaceRole.OWNER:
            owner_count = await self.members.count_by_workspace_and_role(workspace_id, WorkspaceRole.OWNER)
            if owner_count <= 1:
                raise ConflictError(
                    "The sole owner cannot leave the workspace. Transfer ownership or delete it instead."
                )

        old_role = to_jsonable(member.role)
        await self.members.delete(member)

        await self.audit.record(
            workspace_id,
            user_id,
            "member.removed",
            "user",
            user_id,
            {"role": old_role},
            None,
            ip_address,
            user_agent,
        )

        await self.session.commit()
