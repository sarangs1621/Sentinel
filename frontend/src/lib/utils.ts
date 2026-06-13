export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(iso);
}

export function formatMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function formatUptime(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return "—";
  return `${pct.toFixed(2)}%`;
}

export function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    up: "badge-up",
    down: "badge-down",
    pending: "badge-pending",
    success: "badge-success",
    failure: "badge-failure",
    open: "badge-open",
    investigating: "badge-investigating",
    resolved: "badge-resolved",
    critical: "badge-critical",
    major: "badge-major",
    minor: "badge-minor",
    sent: "badge-success",
    failed: "badge-failure",
  };
  return map[status] || "badge-neutral";
}

export function getInitials(name: string | null | undefined): string {
  if (!name) return "?";
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

export function monitorTypeIcon(type: string): string {
  const map: Record<string, string> = {
    http: "🌐",
    tcp: "🔌",
    ping: "📡",
  };
  return map[type] || "🔍";
}

export function channelTypeIcon(type: string): string {
  return type === "email" ? "📧" : "🔗";
}
