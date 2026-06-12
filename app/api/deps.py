import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import TokenType, decode_token
from app.db.session import get_db
from app.models.enums import WorkspaceRole
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.repositories.user import UserRepository
from app.services.api_key import ApiKeyService
from app.services.cache import CacheService
from app.services.workspace import WorkspaceService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]
OptionalToken = Annotated[str | None, Depends(optional_oauth2_scheme)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbSession,
) -> User:
    """Resolve the authenticated user from a Bearer access token."""
    try:
        payload = decode_token(token)
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Could not validate credentials.") from exc

    if payload.get("type") != TokenType.ACCESS.value:
        raise AuthenticationError("Invalid token type.")

    jti = payload.get("jti")
    if jti is not None and await CacheService().is_token_denylisted(jti):
        raise AuthenticationError("Token has been revoked.")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Invalid token payload.") from exc

    user = await UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive.")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_workspace_membership(
    workspace_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> tuple[Workspace, WorkspaceMember]:
    """Resolve the workspace and the current user's membership in it.

    Raises NotFoundError (-> 404) if the workspace doesn't exist, or
    PermissionDeniedError (-> 403) if the user is not a member.
    """
    return await WorkspaceService(db).get_workspace_and_membership(workspace_id, current_user.id)


WorkspaceMembership = Annotated[tuple[Workspace, WorkspaceMember], Depends(get_workspace_membership)]


async def get_workspace_via_membership_or_api_key(
    workspace_id: uuid.UUID,
    db: DbSession,
    token: OptionalToken,
    api_key: Annotated[str | None, Depends(api_key_header)] = None,
) -> tuple[Workspace, WorkspaceMember | None]:
    """Resolve the workspace via either a JWT-authenticated membership or a
    workspace-scoped API key (`X-API-Key` header), for machine-to-machine
    endpoints such as check recording."""
    if api_key is not None:
        workspace = await ApiKeyService(db).authenticate(workspace_id, api_key)
        if workspace is None:
            raise AuthenticationError("Invalid or revoked API key.")
        return workspace, None

    if token is None:
        raise AuthenticationError("Not authenticated.")

    current_user = await get_current_user(token, db)
    return await get_workspace_membership(workspace_id, current_user, db)


WorkspaceMembershipOrApiKey = Annotated[
    tuple[Workspace, WorkspaceMember | None], Depends(get_workspace_via_membership_or_api_key)
]


def require_role(
    *roles: WorkspaceRole,
) -> Callable[[WorkspaceMembership], Awaitable[tuple[Workspace, WorkspaceMember]]]:
    """Dependency factory restricting an endpoint to specific workspace roles."""

    async def checker(membership: WorkspaceMembership) -> tuple[Workspace, WorkspaceMember]:
        _, member = membership
        if member.role not in roles:
            raise PermissionDeniedError("You do not have permission to perform this action.")
        return membership

    return checker


AdminOrOwner = Annotated[
    tuple[Workspace, WorkspaceMember],
    Depends(require_role(WorkspaceRole.OWNER, WorkspaceRole.ADMIN)),
]
OwnerOnly = Annotated[
    tuple[Workspace, WorkspaceMember],
    Depends(require_role(WorkspaceRole.OWNER)),
]


@dataclass(frozen=True)
class AuditContext:
    """The requesting client's IP address and user agent, for audit logging."""

    ip_address: str | None
    user_agent: str | None


def get_audit_context(request: Request) -> AuditContext:
    return AuditContext(
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


AuditContextDep = Annotated[AuditContext, Depends(get_audit_context)]
