"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  apiGetMonitor,
  apiGetLatency,
  apiGetUptime,
  apiListChecks,
  apiListIncidents,
  apiUpdateMonitor,
  type Monitor,
  type LatencyMetrics,
  type UptimeReport,
  type Check,
  type Incident,
} from "@/lib/api";
import {
  statusBadgeClass,
  formatMs,
  formatUptime,
  formatRelative,
  formatDateTime,
  monitorTypeIcon,
} from "@/lib/utils";
import MonitorModal from "@/components/MonitorModal";

export default function MonitorDetailPage() {
  const params = useParams();
  const router = useRouter();
  const wsId = params.id as string;
  const monitorId = params.monitorId as string;

  const [monitor, setMonitor] = useState<Monitor | null>(null);
  const [latency, setLatency] = useState<LatencyMetrics | null>(null);
  const [uptime, setUptime] = useState<UptimeReport | null>(null);
  const [checks, setChecks] = useState<Check[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [showEdit, setShowEdit] = useState(false);
  const [toggling, setToggling] = useState(false);

  const canvasRef = useRef<HTMLCanvasElement>(null);

  async function handleToggleActive() {
    if (!monitor) return;
    setToggling(true);
    try {
      const updated = await apiUpdateMonitor(wsId, monitor.id, { is_active: !monitor.is_active });
      setMonitor(updated);
    } catch { /* ignore */ } finally {
      setToggling(false);
    }
  }

  useEffect(() => {
    Promise.all([
      apiGetMonitor(wsId, monitorId),
      apiGetLatency(wsId, monitorId),
      apiGetUptime(wsId, monitorId),
      apiListChecks(wsId, monitorId),
      apiListIncidents(wsId),
    ])
      .then(([m, lat, up, ch, inc]) => {
        setMonitor(m);
        setLatency(lat);
        setUptime(up);
        setChecks(ch);
        setIncidents(inc.filter((i) => i.monitor_id === monitorId));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [wsId, monitorId]);

  // Draw latency chart
  const drawChart = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || checks.length === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;
    const padding = { top: 20, right: 20, bottom: 30, left: 50 };
    const chartW = w - padding.left - padding.right;
    const chartH = h - padding.top - padding.bottom;

    // Filter checks with response times
    const dataPoints = checks
      .filter((c) => c.response_time_ms !== null)
      .slice(-50)
      .reverse();

    if (dataPoints.length === 0) return;

    const values = dataPoints.map((c) => c.response_time_ms!);
    const maxVal = Math.max(...values) * 1.2 || 100;

    // Clear
    ctx.clearRect(0, 0, w, h);

    // Grid lines
    ctx.strokeStyle = "rgba(99, 115, 148, 0.1)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (chartH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(w - padding.right, y);
      ctx.stroke();

      // Y labels
      ctx.fillStyle = "#64748b";
      ctx.font = "11px Inter, sans-serif";
      ctx.textAlign = "right";
      const val = Math.round(maxVal - (maxVal / 4) * i);
      ctx.fillText(`${val}ms`, padding.left - 8, y + 4);
    }

    // Draw area + line
    const gradient = ctx.createLinearGradient(0, padding.top, 0, h - padding.bottom);
    gradient.addColorStop(0, "rgba(99, 102, 241, 0.3)");
    gradient.addColorStop(1, "rgba(99, 102, 241, 0)");

    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top + chartH);

    dataPoints.forEach((point, i) => {
      const x = padding.left + (chartW / (dataPoints.length - 1 || 1)) * i;
      const y = padding.top + chartH - (point.response_time_ms! / maxVal) * chartH;
      if (i === 0) ctx.lineTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.lineTo(padding.left + chartW, padding.top + chartH);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Line
    ctx.beginPath();
    dataPoints.forEach((point, i) => {
      const x = padding.left + (chartW / (dataPoints.length - 1 || 1)) * i;
      const y = padding.top + chartH - (point.response_time_ms! / maxVal) * chartH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = "#6366f1";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Dots
    dataPoints.forEach((point, i) => {
      const x = padding.left + (chartW / (dataPoints.length - 1 || 1)) * i;
      const y = padding.top + chartH - (point.response_time_ms! / maxVal) * chartH;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fillStyle = point.status === "success" ? "#10b981" : "#ef4444";
      ctx.fill();
    });
  }, [checks]);

  useEffect(() => {
    drawChart();
    window.addEventListener("resize", drawChart);
    return () => window.removeEventListener("resize", drawChart);
  }, [drawChart]);

  if (loading) {
    return (
      <div>
        <div className="page-header"><h1 className="page-title">Monitor Details</h1></div>
        <div className="metrics-grid">{[1, 2, 3, 4].map((i) => <div key={i} className="glass-card skeleton skeleton-card" />)}</div>
      </div>
    );
  }

  if (!monitor) {
    return (
      <div className="empty-state">
        <div className="empty-state-title">Monitor not found</div>
        <button className="btn btn-primary" onClick={() => router.back()}>Go back</button>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <div className="flex items-center gap-3" style={{ marginBottom: 4 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => router.push(`/workspaces/${wsId}/monitors`)}>← Back</button>
          </div>
          <h1 className="page-title flex items-center gap-3">
            {monitorTypeIcon(monitor.monitor_type)}
            {monitor.name}
            <span className={`badge ${statusBadgeClass(monitor.status)}`}>
              <span className="status-dot" />{monitor.status}
            </span>
            {!monitor.is_active && <span className="badge badge-neutral">⏸ Paused</span>}
          </h1>
          <p className="page-subtitle font-mono">{monitor.target}</p>
        </div>
        <div className="flex gap-3">
          <button className="btn btn-secondary" onClick={handleToggleActive} disabled={toggling}>
            {monitor.is_active ? "⏸ Pause" : "▶ Resume"}
          </button>
          <button className="btn btn-secondary" onClick={() => setShowEdit(true)}>
            ✏️ Edit
          </button>
        </div>
      </div>

      {showEdit && (
        <MonitorModal
          wsId={wsId}
          monitor={monitor}
          onClose={() => setShowEdit(false)}
          onSaved={(updated) => {
            setShowEdit(false);
            setMonitor(updated);
          }}
        />
      )}

      {/* Metric Cards */}
      <div className="metrics-grid stagger-children">
        <div className="glass-card metric-card">
          <div className="metric-label">✅ Uptime</div>
          <div className="metric-value" style={{ color: (uptime?.uptime_percentage ?? 0) >= 99 ? "var(--status-up)" : "var(--text-primary)" }}>
            {formatUptime(uptime?.uptime_percentage)}
          </div>
          <div className="metric-sub">
            {uptime?.successful_checks ?? 0}/{uptime?.total_checks ?? 0} checks passed
          </div>
        </div>

        <div className="glass-card metric-card">
          <div className="metric-label">⚡ Avg Latency</div>
          <div className="metric-value">{formatMs(latency?.avg_response_time_ms)}</div>
          <div className="metric-sub">
            p95: {formatMs(latency?.p95_response_time_ms)} · p99: {formatMs(latency?.p99_response_time_ms)}
          </div>
        </div>

        <div className="glass-card metric-card">
          <div className="metric-label">📊 Response Range</div>
          <div className="metric-value">{formatMs(latency?.min_response_time_ms)}</div>
          <div className="metric-sub">
            min → max: {formatMs(latency?.max_response_time_ms)}
          </div>
        </div>

        <div className="glass-card metric-card">
          <div className="metric-label">🔔 Incidents</div>
          <div className="metric-value">{uptime?.incidents_count ?? 0}</div>
          <div className="metric-sub">
            Downtime: {uptime?.total_downtime_seconds ? `${Math.round(uptime.total_downtime_seconds / 60)}min` : "0min"}
          </div>
        </div>
      </div>

      {/* Latency Chart */}
      <div className="glass-card" style={{ padding: 20, marginTop: 24 }}>
        <h3 style={{ fontSize: "0.9375rem", fontWeight: 600, marginBottom: 16 }}>Response Time</h3>
        {checks.filter((c) => c.response_time_ms !== null).length > 0 ? (
          <div className="chart-container">
            <canvas ref={canvasRef} style={{ width: "100%", height: "100%" }} />
          </div>
        ) : (
          <div className="empty-state" style={{ padding: 40 }}>
            <div className="text-muted">No check data available yet</div>
          </div>
        )}
      </div>

      {/* Check History */}
      <div style={{ marginTop: 24 }}>
        <h3 style={{ fontSize: "0.9375rem", fontWeight: 600, marginBottom: 16 }}>Recent Checks</h3>
        {checks.length === 0 ? (
          <div className="glass-card empty-state" style={{ padding: 40 }}>
            <div className="text-muted">No checks recorded yet</div>
          </div>
        ) : (
          <div className="table-wrapper glass-card" style={{ padding: 0 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Response Time</th>
                  <th>Error</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {checks.slice(0, 20).map((c) => (
                  <tr key={c.id}>
                    <td>
                      <span className={`badge ${statusBadgeClass(c.status)}`}>{c.status}</span>
                    </td>
                    <td>{formatMs(c.response_time_ms)}</td>
                    <td className="truncate" style={{ maxWidth: 300 }}>{c.error_message || "—"}</td>
                    <td>{formatDateTime(c.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Incidents for this monitor */}
      {incidents.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <h3 style={{ fontSize: "0.9375rem", fontWeight: 600, marginBottom: 16 }}>Incident History</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {incidents.map((inc) => (
              <div key={inc.id} className="glass-card" style={{ padding: "12px 16px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <span style={{ fontWeight: 500 }}>{inc.title}</span>
                  <span className="text-xs text-muted" style={{ marginLeft: 12 }}>{formatRelative(inc.created_at)}</span>
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
