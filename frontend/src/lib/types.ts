export type WorkspaceRole = "owner" | "admin" | "member";
export type MonitorType = "http" | "tcp" | "ping";
export type MonitorStatus = "pending" | "up" | "down";
export type CheckStatus = "success" | "failure";
export type IncidentStatus = "open" | "investigating" | "resolved";
export type IncidentSeverity = "minor" | "major" | "critical";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface Token {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Workspace {
  id: string;
  name: string;
  description: string | null;
  slug: string;
  invite_code: string | null;
  role: WorkspaceRole;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceMember {
  user_id: string;
  email: string;
  full_name: string | null;
  role: WorkspaceRole;
  created_at: string;
}

export interface Monitor {
  id: string;
  workspace_id: string;
  name: string;
  monitor_type: MonitorType;
  target: string;
  check_interval_seconds: number;
  failure_threshold: number;
  consecutive_failures: number;
  last_checked_at: string | null;
  status: MonitorStatus;
  is_active: boolean;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
  last_response_time_ms: number | null;
}

export interface MonitorCreateInput {
  name: string;
  monitor_type: MonitorType;
  target: string;
  check_interval_seconds: number;
  failure_threshold: number;
  is_active: boolean;
}

export interface MonitorUpdateInput {
  name?: string;
  target?: string;
  check_interval_seconds?: number;
  failure_threshold?: number;
  is_active?: boolean;
}

export interface Check {
  id: string;
  monitor_id: string;
  status: CheckStatus;
  response_time_ms: number | null;
  error_message: string | null;
  created_at: string;
}

export interface Incident {
  id: string;
  workspace_id: string;
  monitor_id: string;
  title: string;
  status: IncidentStatus;
  severity: IncidentSeverity;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

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

export interface WorkspaceDashboard {
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

export interface ApiErrorBody {
  detail?: string | { msg: string; loc?: (string | number)[] }[];
}
