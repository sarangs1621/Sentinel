"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  apiListMonitors,
  apiUpdateMonitor,
  apiDeleteMonitor,
  type Monitor,
} from "@/lib/api";
import {
  statusBadgeClass,
  formatRelative,
  monitorTypeIcon,
} from "@/lib/utils";
import MonitorModal from "@/components/MonitorModal";

export default function MonitorsPage() {
  const params = useParams();
  const router = useRouter();
  const wsId = params.id as string;

  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editingMonitor, setEditingMonitor] = useState<Monitor | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  function loadMonitors() {
    apiListMonitors(wsId)
      .then(setMonitors)
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadMonitors();
  }, [wsId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleDelete(monitorId: string) {
    if (!confirm("Delete this monitor? This action cannot be undone.")) return;
    try {
      await apiDeleteMonitor(wsId, monitorId);
      loadMonitors();
    } catch { /* ignore */ }
  }

  async function handleToggleActive(monitor: Monitor) {
    setTogglingId(monitor.id);
    try {
      await apiUpdateMonitor(wsId, monitor.id, { is_active: !monitor.is_active });
      loadMonitors();
    } catch { /* ignore */ } finally {
      setTogglingId(null);
    }
  }

  return (
    <>
      <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Monitors</h1>
          <p className="page-subtitle">{monitors.length} monitors configured</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          + New monitor
        </button>
      </div>

      </div>

      {/* Create Modal */}
      {showCreate && (
        <MonitorModal
          wsId={wsId}
          onClose={() => setShowCreate(false)}
          onSaved={() => {
            setShowCreate(false);
            loadMonitors();
          }}
        />
      )}

      {/* Edit Modal */}
      {editingMonitor && (
        <MonitorModal
          wsId={wsId}
          monitor={editingMonitor}
          onClose={() => setEditingMonitor(null)}
          onSaved={() => {
            setEditingMonitor(null);
            loadMonitors();
          }}
        />
      )}

      {/* Monitors List */}
      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {[1, 2, 3].map((i) => (
            <div key={i} className="glass-card skeleton" style={{ height: 72 }} />
          ))}
        </div>
      ) : monitors.length === 0 ? (
        <div className="glass-card empty-state">
          <div className="empty-state-icon">🖥️</div>
          <div className="empty-state-title">No monitors yet</div>
          <div className="empty-state-desc">
            Create your first monitor to track the health and uptime of your services.
          </div>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            + New monitor
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }} className="stagger-children">
          {monitors.map((m) => (
            <div
              key={m.id}
              className="glass-card"
              style={{ padding: "16px 20px", display: "flex", alignItems: "center", gap: 16, cursor: "pointer", opacity: m.is_active ? 1 : 0.6 }}
              onClick={() => router.push(`/workspaces/${wsId}/monitors/${m.id}`)}
            >
              <div style={{ fontSize: "1.5rem" }}>{monitorTypeIcon(m.monitor_type)}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>{m.name}</div>
                <div className="text-xs text-muted font-mono truncate">{m.target}</div>
              </div>
              <div className="flex items-center gap-3" style={{ flexShrink: 0 }}>
                {!m.is_active && <span className="badge badge-neutral">⏸ Paused</span>}
                <span className={`badge ${statusBadgeClass(m.status)}`}>
                  <span className="status-dot" />
                  {m.status}
                </span>
                <span className="text-xs text-muted" style={{ minWidth: 60, textAlign: "right" }}>
                  {m.last_checked_at ? formatRelative(m.last_checked_at) : "—"}
                </span>
                <button
                  className="btn btn-ghost btn-icon btn-sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleToggleActive(m);
                  }}
                  disabled={togglingId === m.id}
                  title={m.is_active ? "Pause monitor" : "Resume monitor"}
                >
                  {m.is_active ? "⏸" : "▶"}
                </button>
                <button
                  className="btn btn-ghost btn-icon btn-sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditingMonitor(m);
                  }}
                  title="Edit"
                >
                  ✏️
                </button>
                <button
                  className="btn btn-ghost btn-icon btn-sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(m.id);
                  }}
                  title="Delete"
                >
                  🗑
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
