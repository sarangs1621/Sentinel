import { API_BASE_URL } from "./config";
import type {
  ApiErrorBody,
  Check,
  Incident,
  IncidentStatus,
  LatencyMetrics,
  Monitor,
  MonitorCreateInput,
  MonitorUpdateInput,
  Token,
  UptimeReport,
  User,
  Workspace,
  WorkspaceDashboard,
  WorkspaceMember,
} from "./types";

const ACCESS_TOKEN_KEY = "sentinel.access_token";
const REFRESH_TOKEN_KEY = "sentinel.refresh_token";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(token: Token): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token.access_token);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, token.refresh_token);
}

export function clearTokens(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function extractMessage(body: unknown, fallback: string): string {
  const detail = (body as ApiErrorBody | null)?.detail;
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join(", ") || fallback;
  }
  return fallback;
}

let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) return false;
    const token: Token = await response.json();
    setTokens(token);
    return true;
  } catch {
    return false;
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: BodyInit | object | null;
  /** Set to false for endpoints that must not attach/refresh the access token. */
  auth?: boolean;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { auth = true, headers, body, ...rest } = options;

  const isPlainObjectBody =
    body !== null && typeof body === "object" && !(body instanceof URLSearchParams) && !(body instanceof FormData);
  const preparedBody = isPlainObjectBody ? JSON.stringify(body) : (body as BodyInit | null | undefined);

  const buildHeaders = () => {
    const finalHeaders = new Headers(headers);
    if (isPlainObjectBody && !finalHeaders.has("Content-Type")) {
      finalHeaders.set("Content-Type", "application/json");
    }
    if (auth) {
      const token = getAccessToken();
      if (token) finalHeaders.set("Authorization", `Bearer ${token}`);
    }
    return finalHeaders;
  };

  const doFetch = () =>
    fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      body: preparedBody,
      headers: buildHeaders(),
    });

  let response = await doFetch();

  if (response.status === 401 && auth && path !== "/auth/refresh") {
    refreshPromise ??= refreshAccessToken().finally(() => {
      refreshPromise = null;
    });
    const refreshed = await refreshPromise;

    if (refreshed) {
      response = await doFetch();
    } else {
      clearTokens();
      if (typeof window !== "undefined") {
        window.dispatchEvent(new Event("sentinel:unauthorized"));
      }
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    throw new ApiError(response.status, extractMessage(data, response.statusText));
  }

  return data as T;
}

// ---------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------

export const authApi = {
  login: (email: string, password: string) =>
    apiFetch<Token>("/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: email, password }),
      auth: false,
    }),

  register: (data: { email: string; password: string; full_name?: string }) =>
    apiFetch<User>("/auth/register", { method: "POST", body: data, auth: false }),

  refresh: () => refreshAccessToken(),

  logout: () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return Promise.resolve();
    return apiFetch<void>("/auth/logout", {
      method: "POST",
      body: { refresh_token: refreshToken },
    });
  },

  me: () => apiFetch<User>("/users/me"),
};

// ---------------------------------------------------------------------
// Workspaces
// ---------------------------------------------------------------------

export const workspaceApi = {
  list: () => apiFetch<Workspace[]>("/workspaces"),

  get: (workspaceId: string) => apiFetch<Workspace>(`/workspaces/${workspaceId}`),

  create: (data: { name: string; description?: string }) =>
    apiFetch<Workspace>("/workspaces", { method: "POST", body: data }),

  join: (inviteCode: string) =>
    apiFetch<Workspace>("/workspaces/join", { method: "POST", body: { invite_code: inviteCode } }),

  regenerateInviteCode: (workspaceId: string) =>
    apiFetch<Workspace>(`/workspaces/${workspaceId}/invite-code/regenerate`, { method: "POST" }),

  members: (workspaceId: string) => apiFetch<WorkspaceMember[]>(`/workspaces/${workspaceId}/members`),
};

// ---------------------------------------------------------------------
// Monitors
// ---------------------------------------------------------------------

export const monitorApi = {
  list: (workspaceId: string) => apiFetch<Monitor[]>(`/workspaces/${workspaceId}/monitors`),

  get: (workspaceId: string, monitorId: string) =>
    apiFetch<Monitor>(`/workspaces/${workspaceId}/monitors/${monitorId}`),

  create: (workspaceId: string, data: MonitorCreateInput) =>
    apiFetch<Monitor>(`/workspaces/${workspaceId}/monitors`, { method: "POST", body: data }),

  update: (workspaceId: string, monitorId: string, data: MonitorUpdateInput) =>
    apiFetch<Monitor>(`/workspaces/${workspaceId}/monitors/${monitorId}`, { method: "PATCH", body: data }),

  remove: (workspaceId: string, monitorId: string) =>
    apiFetch<void>(`/workspaces/${workspaceId}/monitors/${monitorId}`, { method: "DELETE" }),

  checks: (workspaceId: string, monitorId: string) =>
    apiFetch<Check[]>(`/workspaces/${workspaceId}/monitors/${monitorId}/checks`),

  latency: (workspaceId: string, monitorId: string) =>
    apiFetch<LatencyMetrics>(`/workspaces/${workspaceId}/monitors/${monitorId}/metrics/latency`),

  uptime: (workspaceId: string, monitorId: string) =>
    apiFetch<UptimeReport>(`/workspaces/${workspaceId}/monitors/${monitorId}/metrics/uptime`),
};

// ---------------------------------------------------------------------
// Incidents
// ---------------------------------------------------------------------

export const incidentApi = {
  list: (workspaceId: string) => apiFetch<Incident[]>(`/workspaces/${workspaceId}/incidents`),

  get: (workspaceId: string, incidentId: string) =>
    apiFetch<Incident>(`/workspaces/${workspaceId}/incidents/${incidentId}`),

  update: (workspaceId: string, incidentId: string, newStatus: IncidentStatus) =>
    apiFetch<Incident>(`/workspaces/${workspaceId}/incidents/${incidentId}`, {
      method: "PATCH",
      body: { status: newStatus },
    }),
};

// ---------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------

export const dashboardApi = {
  get: (workspaceId: string) => apiFetch<WorkspaceDashboard>(`/workspaces/${workspaceId}/dashboard`),
};
