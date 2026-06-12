import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.models.enums import WorkspaceRole
from app.models.monitor import Monitor
from app.models.user import User
from app.models.workspace_member import WorkspaceMember
from app.repositories.monitor import MonitorRepository
from app.schemas.monitor import MonitorCreate, MonitorRead, MonitorUpdate, validate_target_for_type
from app.services.audit_log import AuditLogService, to_jsonable
from app.services.cache import CacheService

_PRIVILEGED_ROLES = (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)


class MonitorService:
    def __init__(self, session: AsyncSession, cache: CacheService | None = None) -> None:
        self.session = session
        self.monitors = MonitorRepository(session)
        self.audit = AuditLogService(session)
        self.cache = cache if cache is not None else CacheService()

    async def _to_read(self, monitor: Monitor) -> MonitorRead:
        data = MonitorRead.model_validate(monitor).model_dump()
        status_cache = await self.cache.get_monitor_status(monitor.id)
        if status_cache is not None:
            data["last_response_time_ms"] = status_cache.get("last_response_time_ms")
        return MonitorRead.model_validate(data)

    async def create_monitor(
        self,
        workspace_id: uuid.UUID,
        user: User,
        data: MonitorCreate,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> MonitorRead:
        if await self.monitors.exists_active(workspace_id, data.monitor_type, data.target):
            raise ConflictError("A monitor with this type and target already exists in this workspace.")

        monitor = Monitor(
            workspace_id=workspace_id,
            created_by_user_id=user.id,
            name=data.name,
            monitor_type=data.monitor_type,
            target=data.target,
            check_interval_seconds=data.check_interval_seconds,
            failure_threshold=data.failure_threshold,
            is_active=data.is_active,
        )
        self.monitors.add(monitor)
        await self.session.flush()

        await self.audit.record(
            workspace_id,
            user.id,
            "monitor.created",
            "monitor",
            monitor.id,
            None,
            {
                "name": monitor.name,
                "monitor_type": to_jsonable(monitor.monitor_type),
                "target": monitor.target,
                "check_interval_seconds": monitor.check_interval_seconds,
                "failure_threshold": monitor.failure_threshold,
                "is_active": monitor.is_active,
            },
            ip_address,
            user_agent,
        )

        await self.session.commit()
        await self.session.refresh(monitor)
        await self.cache.invalidate_dashboard(workspace_id)
        return await self._to_read(monitor)

    async def list_monitors(self, workspace_id: uuid.UUID) -> list[MonitorRead]:
        monitors = await self.monitors.list_by_workspace(workspace_id)
        return [await self._to_read(m) for m in monitors]

    async def get_monitor(self, workspace_id: uuid.UUID, monitor_id: uuid.UUID) -> MonitorRead:
        monitor = await self.monitors.get_active_by_id(workspace_id, monitor_id)
        if monitor is None:
            raise NotFoundError("Monitor not found.")
        return await self._to_read(monitor)

    async def _get_for_mutation(
        self, workspace_id: uuid.UUID, monitor_id: uuid.UUID, acting_member: WorkspaceMember, user: User
    ) -> Monitor:
        monitor = await self.monitors.get_active_by_id(workspace_id, monitor_id)
        if monitor is None:
            raise NotFoundError("Monitor not found.")

        is_privileged = acting_member.role in _PRIVILEGED_ROLES
        if not is_privileged and monitor.created_by_user_id != user.id:
            raise PermissionDeniedError("Only the monitor's creator or a workspace admin/owner can do this.")
        return monitor

    async def update_monitor(
        self,
        workspace_id: uuid.UUID,
        monitor_id: uuid.UUID,
        data: MonitorUpdate,
        acting_member: WorkspaceMember,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> MonitorRead:
        monitor = await self._get_for_mutation(workspace_id, monitor_id, acting_member, user)

        updates = data.model_dump(exclude_unset=True)
        new_target = updates.get("target")
        if new_target is not None and new_target != monitor.target:
            validate_target_for_type(monitor.monitor_type, new_target)
            if await self.monitors.exists_active(workspace_id, monitor.monitor_type, new_target, exclude_id=monitor.id):
                raise ConflictError("A monitor with this type and target already exists in this workspace.")

        old_values = {field: to_jsonable(getattr(monitor, field)) for field in updates}

        for field, value in updates.items():
            setattr(monitor, field, value)

        new_values = {field: to_jsonable(getattr(monitor, field)) for field in updates}

        await self.audit.record(
            workspace_id,
            user.id,
            "monitor.updated",
            "monitor",
            monitor.id,
            old_values,
            new_values,
            ip_address,
            user_agent,
        )

        if "is_active" in updates and old_values["is_active"] != new_values["is_active"]:
            action = "monitor.enabled" if new_values["is_active"] else "monitor.disabled"
            await self.audit.record(
                workspace_id,
                user.id,
                action,
                "monitor",
                monitor.id,
                {"is_active": old_values["is_active"]},
                {"is_active": new_values["is_active"]},
                ip_address,
                user_agent,
            )

        await self.session.commit()
        await self.session.refresh(monitor)
        return await self._to_read(monitor)

    async def delete_monitor(
        self,
        workspace_id: uuid.UUID,
        monitor_id: uuid.UUID,
        acting_member: WorkspaceMember,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        monitor = await self._get_for_mutation(workspace_id, monitor_id, acting_member, user)

        old_values = {
            "name": monitor.name,
            "monitor_type": to_jsonable(monitor.monitor_type),
            "target": monitor.target,
            "is_active": monitor.is_active,
        }

        monitor.deleted_at = datetime.now(UTC)
        await self.audit.record(
            workspace_id, user.id, "monitor.deleted", "monitor", monitor.id, old_values, None, ip_address, user_agent
        )
        await self.session.commit()
        await self.cache.invalidate_dashboard(workspace_id)
