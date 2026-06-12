from fastapi import APIRouter

from app.api.v1.endpoints import (
    alert_rules,
    api_keys,
    audit_logs,
    auth,
    checks,
    dashboard,
    incidents,
    metrics,
    monitors,
    notifications,
    users,
    workspaces,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(monitors.router, prefix="/workspaces/{workspace_id}/monitors", tags=["monitors"])
api_router.include_router(audit_logs.router, prefix="/workspaces/{workspace_id}/audit-logs", tags=["audit-logs"])
api_router.include_router(
    checks.router, prefix="/workspaces/{workspace_id}/monitors/{monitor_id}/checks", tags=["checks"]
)
api_router.include_router(
    metrics.router, prefix="/workspaces/{workspace_id}/monitors/{monitor_id}/metrics", tags=["metrics"]
)
api_router.include_router(incidents.router, prefix="/workspaces/{workspace_id}/incidents", tags=["incidents"])
api_router.include_router(
    alert_rules.router, prefix="/workspaces/{workspace_id}/alert-rules", tags=["alerting"]
)
api_router.include_router(
    notifications.router, prefix="/workspaces/{workspace_id}/notifications", tags=["alerting"]
)
api_router.include_router(dashboard.router, prefix="/workspaces/{workspace_id}/dashboard", tags=["dashboard"])
api_router.include_router(
    api_keys.router, prefix="/workspaces/{workspace_id}/api-keys", tags=["api-keys"]
)
