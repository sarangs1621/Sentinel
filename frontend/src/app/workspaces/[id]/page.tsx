"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiGetDashboard, apiListMonitors, apiListIncidents, type Dashboard, type Monitor, type Incident } from "@/lib/api";
import { statusBadgeClass, formatMs, formatUptime, formatRelative, monitorTypeIcon } from "@/lib/utils";

export default function WorkspaceDashboardPage() {
  const params = useParams();
  const router = useRouter();
  const wsId = params.id as string;
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiGetDashboard(wsId),
      apiListMonitors(wsId),
      apiListIncidents(wsId),
    ])
      .then(([d, m, i]) => {
        setDashboard(d);
        setMonitors(m);
        setIncidents(i);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [wsId]);

  if (loading) {
    return (
      <div>
        <div className="page-header">
          <div>
            <h1 className="page-title">Dashboard</h1>
            <p className="page-subtitle">Loading overview…</p>
          </div>
        </div>
        <div className="metrics-grid">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="glass-card skeleton skeleton-card" />
          ))}
        </div>
      </div>
    );
  }

  const openIncidents = incidents.filter((i) => i.status !== "resolved");

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">
            Last 24 hours overview · {dashboard?.total_monitors ?? 0} monitors
          </p>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="metrics-grid stagger-children">
        <div className="glass-card metric-card">
          <div className="metric-label">📡 Total Monitors</div>
          <div className="metric-value">{dashboard?.total_monitors ?? 0}</div>
          <div className="metric-sub">
            <span style={{ color: "var(--status-up)" }}>{dashboard?.monitor_status_counts.up ?? 0} up</span>
            {" · "}
            <span style={{ color: "var(--status-down)" }}>{dashboard?.monitor_status_counts.down ?? 0} down</span>
            {" · "}
            <span style={{ color: "var(--status-pending)" }}>{dashboard?.monitor_status_counts.pending ?? 0} pending</span>
          </div>
        </div>

        <div className="glass-card metric-card">
          <div className="metric-label">✅ Check Pass Rate</div>
          <div className="metric-value" style={{ color: dashboard?.overall_check_pass_ratio !== null && (dashboard?.overall_check_pass_ratio ?? 0) >= 99 ? "var(--status-up)" : "var(--text-primary)" }}>
            {formatUptime(dashboard?.overall_check_pass_ratio)}
          </div>
          <div className="metric-sub">{dashboard?.total_checks ?? 0} checks in period</div>
        </div>

        <div className="glass-card metric-card">
          <div className="metric-label">⚡ Avg Response Time</div>
          <div className="metric-value">{formatMs(dashboard?.avg_response_time_ms)}</div>
          <div className="metric-sub">Across all monitors</div>
        </div>

        <div className="glass-card metric-card">
          <div className="metric-label">🔔 Active Incidents</div>
          <div className="metric-value" style={{ color: openIncidents.length > 0 ? "var(--status-down)" : "var(--status-up)" }}>
            {openIncidents.length}
          </div>
          <div className="metric-sub">
            {dashboard?.incident_status_counts.open ?? 0} open · {dashboard?.incident_status_counts.investigating ?? 0} investigating
          </div>
        </div>
      </div>

      {/* Monitors Status List */}
      <div style={{ marginTop: 32 }}>
        <h2 style={{ fontSize: "1.125rem", fontWeight: 600, marginBottom: 16 }}>Monitors</h2>
        {monitors.length === 0 ? (
          <div className="glass-card empty-state" style={{ padding: 40 }}>
            <div className="empty-state-icon">🖥️</div>
            <div className="empty-state-title">No monitors yet</div>
            <div className="empty-state-desc">Create your first monitor to start tracking uptime.</div>
            <button className="btn btn-primary" onClick={() => router.push(`/workspaces/${wsId}/monitors`)}>
              + Add monitor
            </button>
          </div>
        ) : (
          <div className="table-wrapper glass-card" style={{ padding: 0 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Response</th>
                  <th>Last Check</th>
                </tr>
              </thead>
              <tbody>
                {monitors.map((m) => (
                  <tr
                    key={m.id}
                    style={{ cursor: "pointer" }}
                    onClick={() => router.push(`/workspaces/${wsId}/monitors/${m.id}`)}
                  >
                    <td style={{ color: "var(--text-primary)", fontWeight: 500 }}>{m.name}</td>
                    <td>
                      <span className="flex items-center gap-2">
                        {monitorTypeIcon(m.monitor_type)} {m.monitor_type.toUpperCase()}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${statusBadgeClass(m.status)}`}>
                        <span className="status-dot" />
                        {m.status}
                      </span>
                    </td>
                    <td>{formatMs(m.last_response_time_ms)}</td>
                    <td>{m.last_checked_at ? formatRelative(m.last_checked_at) : "Never"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Open Incidents */}
      {openIncidents.length > 0 && (
        <div style={{ marginTop: 32 }}>
          <h2 style={{ fontSize: "1.125rem", fontWeight: 600, marginBottom: 16 }}>Active Incidents</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }} className="stagger-children">
            {openIncidents.slice(0, 5).map((inc) => (
              <div
                key={inc.id}
                className="glass-card"
                style={{ padding: "16px 20px", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}
                onClick={() => router.push(`/workspaces/${wsId}/incidents`)}
              >
                <div>
                  <div style={{ fontWeight: 500, marginBottom: 4 }}>{inc.title}</div>
                  <div className="text-xs text-muted">{formatRelative(inc.created_at)}</div>
                </div>
                <div className="flex gap-2">
                  <span className={`badge ${statusBadgeClass(inc.severity)}`}>{inc.severity}</span>
                  <span className={`badge ${statusBadgeClass(inc.status)}`}>{inc.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
