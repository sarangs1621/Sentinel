const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/* ---------- helpers ---------- */

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
}

export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

/* ---------- core fetch wrapper ---------- */

async function refreshAccessToken(): Promise<string | null> {
  const rt = getRefreshToken();
  if (!rt) return null;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    return null;
  }
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!headers["Content-Type"] && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401 && retry) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      return apiFetch<T>(path, options, false);
    }
    clearTokens();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Session expired");
  }

  if (res.status === 204) return undefined as T;

  const body = await res.json().catch(() => ({}));

  if (!res.ok) {
    let errorMessage = `Request failed (${res.status})`;
    if (typeof body.detail === "string") {
      errorMessage = body.detail;
    } else if (Array.isArray(body.detail)) {
      errorMessage = body.detail.map((err: { msg: string }) => {
        let cleanMsg = err.msg;
        if (cleanMsg.startsWith("Value error, ")) {
          cleanMsg = cleanMsg.replace("Value error, ", "");
        }
        return cleanMsg;
      }).join(" | ");
    }
    throw new ApiError(res.status, errorMessage);
  }

  return body as T;
}

/* ---------- Auth ---------- */

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export async function apiLogin(email: string, password: string): Promise<TokenResponse> {
  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);
  const data = await apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function apiRegister(email: string, password: string, fullName?: string): Promise<User> {
  return apiFetch<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name: fullName || null }),
  });
}

export async function apiLogout(): Promise<void> {
  const rt = getRefreshToken();
  if (rt) {
    try {
      await apiFetch("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: rt }),
      });
    } catch { /* ignore */ }
  }
  clearTokens();
}

export async function apiGetMe(): Promise<User> {
  return apiFetch<User>("/users/me");
}

/* ---------- Workspaces ---------- */

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  invite_code: string | null;
  role: string;
  created_at: string;
  updated_at: string;
}

export async function apiListWorkspaces(): Promise<Workspace[]> {
  return apiFetch<Workspace[]>("/workspaces");
}

export async function apiGetWorkspace(id: string): Promise<Workspace> {
  return apiFetch<Workspace>(`/workspaces/${id}`);
}

export async function apiCreateWorkspace(data: { name: string; description?: string; slug?: string }): Promise<Workspace> {
  return apiFetch<Workspace>("/workspaces", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function apiJoinWorkspace(invite_code: string): Promise<Workspace> {
  return apiFetch<Workspace>("/workspaces/join", {
    method: "POST",
    body: JSON.stringify({ invite_code }),
  });
}

export async function apiUpdateWorkspace(id: string, data: { name?: string; description?: string }): Promise<Workspace> {
  return apiFetch<Workspace>(`/workspaces/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function apiDeleteWorkspace(id: string): Promise<void> {
  return apiFetch<void>(`/workspaces/${id}`, { method: "DELETE" });
}

export async function apiRegenerateInviteCode(id: string): Promise<Workspace> {
  return apiFetch<Workspace>(`/workspaces/${id}/invite-code/regenerate`, { method: "POST" });
}

/* ---------- Members ---------- */

export interface WorkspaceMember {
  user_id: string;
  email: string;
  full_name: string | null;
  role: string;
  created_at: string;
}

export async function apiListMembers(wsId: string): Promise<WorkspaceMember[]> {
  return apiFetch<WorkspaceMember[]>(`/workspaces/${wsId}/members`);
}

export async function apiUpdateMemberRole(wsId: string, userId: string, role: string): Promise<WorkspaceMember> {
  return apiFetch<WorkspaceMember>(`/workspaces/${wsId}/members/${userId}`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}

export async function apiRemoveMember(wsId: string, userId: string): Promise<void> {
  return apiFetch<void>(`/workspaces/${wsId}/members/${userId}`, { method: "DELETE" });
}

export async function apiLeaveWorkspace(wsId: string): Promise<void> {
  return apiFetch<void>(`/workspaces/${wsId}/members/me`, { method: "DELETE" });
}

/* ---------- Monitors ---------- */

export interface Monitor {
  id: string;
  workspace_id: string;
  name: string;
  monitor_type: "http" | "tcp" | "ping";
  target: string;
  check_interval_seconds: number;
  failure_threshold: number;
  consecutive_failures: number;
  last_checked_at: string | null;
  status: "pending" | "up" | "down";
  is_active: boolean;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
  last_response_time_ms: number | null;
}

export interface MonitorCreate {
  name: string;
  monitor_type: "http" | "tcp" | "ping";
  target: string;
  check_interval_seconds?: number;
  failure_threshold?: number;
  is_active?: boolean;
}

export interface MonitorUpdate {
  name?: string;
  target?: string;
  check_interval_seconds?: number;
  failure_threshold?: number;
  is_active?: boolean;
}

export async function apiListMonitors(wsId: string): Promise<Monitor[]> {
  return apiFetch<Monitor[]>(`/workspaces/${wsId}/monitors`);
}

export async function apiGetMonitor(wsId: string, monitorId: string): Promise<Monitor> {
  return apiFetch<Monitor>(`/workspaces/${wsId}/monitors/${monitorId}`);
}

export async function apiCreateMonitor(wsId: string, data: MonitorCreate): Promise<Monitor> {
  return apiFetch<Monitor>(`/workspaces/${wsId}/monitors`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function apiUpdateMonitor(wsId: string, monitorId: string, data: MonitorUpdate): Promise<Monitor> {
  return apiFetch<Monitor>(`/workspaces/${wsId}/monitors/${monitorId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function apiDeleteMonitor(wsId: string, monitorId: string): Promise<void> {
  return apiFetch<void>(`/workspaces/${wsId}/monitors/${monitorId}`, { method: "DELETE" });
}

/* ---------- Checks ---------- */

export interface Check {
  id: string;
  monitor_id: string;
  status: "success" | "failure";
  response_time_ms: number | null;
  error_message: string | null;
  created_at: string;
}

export async function apiListChecks(wsId: string, monitorId: string): Promise<Check[]> {
  return apiFetch<Check[]>(`/workspaces/${wsId}/monitors/${monitorId}/checks`);
}

/* ---------- Incidents ---------- */

export interface Incident {
  id: string;
  workspace_id: string;
  monitor_id: string;
  title: string;
  status: "open" | "investigating" | "resolved";
  severity: "critical" | "major" | "minor";
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export async function apiListIncidents(wsId: string): Promise<Incident[]> {
  return apiFetch<Incident[]>(`/workspaces/${wsId}/incidents`);
}

export async function apiGetIncident(wsId: string, incidentId: string): Promise<Incident> {
  return apiFetch<Incident>(`/workspaces/${wsId}/incidents/${incidentId}`);
}

export async function apiUpdateIncident(wsId: string, incidentId: string, status: string): Promise<Incident> {
  return apiFetch<Incident>(`/workspaces/${wsId}/incidents/${incidentId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

/* ---------- Alert Rules ---------- */

export interface AlertRule {
  id: string;
  workspace_id: string;
  name: string;
  channel_type: "webhook" | "email";
  target: string;
  is_enabled: boolean;
  min_severity: "critical" | "major" | "minor" | null;
  created_at: string;
  updated_at: string;
}

export interface AlertRuleCreate {
  name: string;
  channel_type: "webhook" | "email";
  target: string;
  is_enabled?: boolean;
  min_severity?: string | null;
}

export async function apiListAlertRules(wsId: string): Promise<AlertRule[]> {
  return apiFetch<AlertRule[]>(`/workspaces/${wsId}/alert-rules`);
}

export async function apiCreateAlertRule(wsId: string, data: AlertRuleCreate): Promise<AlertRule> {
  return apiFetch<AlertRule>(`/workspaces/${wsId}/alert-rules`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function apiUpdateAlertRule(wsId: string, ruleId: string, data: Partial<AlertRuleCreate>): Promise<AlertRule> {
  return apiFetch<AlertRule>(`/workspaces/${wsId}/alert-rules/${ruleId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function apiDeleteAlertRule(wsId: string, ruleId: string): Promise<void> {
  return apiFetch<void>(`/workspaces/${wsId}/alert-rules/${ruleId}`, { method: "DELETE" });
}

/* ---------- Notifications ---------- */

export interface Notification {
  id: string;
  workspace_id: string;
  incident_id: string;
  alert_rule_id: string;
  event_type: string;
  status: "pending" | "sent" | "failed";
  attempts: number;
  last_attempted_at: string | null;
  response_status_code: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export async function apiListNotifications(wsId: string): Promise<Notification[]> {
  return apiFetch<Notification[]>(`/workspaces/${wsId}/notifications`);
}

/* ---------- Metrics ---------- */

export interface LatencyMetrics {
  monitor_id: string;
  period_start: string;
  period_end: string;
  total_checks: number;
  avg_response_time_ms: number | null;
  min_response_time_ms: number | null;
  max_response_time_ms: number | null;
  p50_response_time_ms: number | null;
  p95_response_time_ms: number | null;
  p99_response_time_ms: number | null;
}

export interface UptimeReport {
  monitor_id: string;
  period_start: string;
  period_end: string;
  total_checks: number;
  successful_checks: number;
  failed_checks: number;
  check_pass_ratio: number | null;
  uptime_percentage: number;
  total_downtime_seconds: number;
  incidents_count: number;
}

export interface Dashboard {
  workspace_id: string;
  period_start: string;
  period_end: string;
  total_monitors: number;
  monitor_status_counts: { pending: number; up: number; down: number };
  incident_status_counts: { open: number; investigating: number; resolved: number };
  total_checks: number;
  overall_check_pass_ratio: number | null;
  avg_response_time_ms: number | null;
}

export async function apiGetLatency(wsId: string, monitorId: string, start?: string, end?: string): Promise<LatencyMetrics> {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const qs = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<LatencyMetrics>(`/workspaces/${wsId}/monitors/${monitorId}/metrics/latency${qs}`);
}

export async function apiGetUptime(wsId: string, monitorId: string, start?: string, end?: string): Promise<UptimeReport> {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const qs = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<UptimeReport>(`/workspaces/${wsId}/monitors/${monitorId}/metrics/uptime${qs}`);
}

export async function apiGetDashboard(wsId: string): Promise<Dashboard> {
  return apiFetch<Dashboard>(`/workspaces/${wsId}/dashboard`);
}

/* ---------- Audit Logs ---------- */

export interface AuditLog {
  id: string;
  workspace_id: string;
  user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export async function apiListAuditLogs(wsId: string): Promise<AuditLog[]> {
  return apiFetch<AuditLog[]>(`/workspaces/${wsId}/audit-logs`);
}

export async function apiSearchAuditLogs(
  wsId: string,
  params: { user_id?: string; action?: string; entity_type?: string; start?: string; end?: string; limit?: number; offset?: number }
): Promise<AuditLog[]> {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) sp.set(k, String(v));
  });
  const qs = sp.toString() ? `?${sp.toString()}` : "";
  return apiFetch<AuditLog[]>(`/workspaces/${wsId}/audit-logs/search${qs}`);
}

/* ---------- API Keys ---------- */

export interface ApiKey {
  id: string;
  workspace_id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface ApiKeyCreated extends ApiKey {
  api_key: string;
}

export async function apiListApiKeys(wsId: string): Promise<ApiKey[]> {
  return apiFetch<ApiKey[]>(`/workspaces/${wsId}/api-keys`);
}

export async function apiCreateApiKey(wsId: string, name: string): Promise<ApiKeyCreated> {
  return apiFetch<ApiKeyCreated>(`/workspaces/${wsId}/api-keys`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function apiRevokeApiKey(wsId: string, apiKeyId: string): Promise<void> {
  return apiFetch<void>(`/workspaces/${wsId}/api-keys/${apiKeyId}`, { method: "DELETE" });
}
