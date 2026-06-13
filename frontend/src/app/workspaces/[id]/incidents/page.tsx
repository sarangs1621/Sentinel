"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  apiListIncidents,
  apiUpdateIncident,
  ApiError,
  type Incident,
} from "@/lib/api";
import {
  statusBadgeClass,
  formatRelative,
  formatDateTime,
} from "@/lib/utils";

export default function IncidentsPage() {
  const params = useParams();
  const wsId = params.id as string;

  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [actionError, setActionError] = useState("");

  function loadIncidents() {
    apiListIncidents(wsId)
      .then(setIncidents)
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadIncidents();
  }, [wsId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleAction(incidentId: string, status: string) {
    setActionError("");
    try {
      await apiUpdateIncident(wsId, incidentId, status);
      loadIncidents();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : "Failed to update incident");
    }
  }

  const filtered =
    filter === "all"
      ? incidents
      : incidents.filter((i) => i.status === filter);

  const counts = {
    all: incidents.length,
    open: incidents.filter((i) => i.status === "open").length,
    investigating: incidents.filter((i) => i.status === "investigating").length,
    resolved: incidents.filter((i) => i.status === "resolved").length,
  };

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Incidents</h1>
          <p className="page-subtitle">
            {counts.open + counts.investigating} active incidents
          </p>
        </div>
      </div>

      {actionError && (
        <div className="auth-error" style={{ marginBottom: 16 }}>{actionError}</div>
      )}

      {/* Filter Tabs */}
      <div className="tabs">
        {(["all", "open", "investigating", "resolved"] as const).map((tab) => (
          <button
            key={tab}
            className={`tab ${filter === tab ? "active" : ""}`}
            onClick={() => setFilter(tab)}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
            <span style={{ marginLeft: 6, opacity: 0.6, fontSize: "0.75rem" }}>
              {counts[tab]}
            </span>
          </button>
        ))}
      </div>

      {/* Incidents List */}
      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {[1, 2, 3].map((i) => (
            <div key={i} className="glass-card skeleton" style={{ height: 80 }} />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-card empty-state">
          <div className="empty-state-icon">🎉</div>
          <div className="empty-state-title">
            {filter === "all" ? "No incidents" : `No ${filter} incidents`}
          </div>
          <div className="empty-state-desc">
            {filter === "all"
              ? "All systems are operating normally."
              : "No incidents match this filter."}
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }} className="stagger-children">
          {filtered.map((inc) => (
            <div
              key={inc.id}
              className="glass-card"
              style={{ padding: "16px 20px" }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: "0.9375rem", marginBottom: 4, color: "var(--text-primary)" }}>
                    {inc.title}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted">
                    <span>Created {formatRelative(inc.created_at)}</span>
                    {inc.resolved_at && <span>· Resolved {formatDateTime(inc.resolved_at)}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2" style={{ flexShrink: 0 }}>
                  <span className={`badge ${statusBadgeClass(inc.severity)}`}>{inc.severity}</span>
                  <span className={`badge ${statusBadgeClass(inc.status)}`}>
                    <span className="status-dot" />{inc.status}
                  </span>
                </div>
              </div>

              {/* Actions */}
              {inc.status !== "resolved" && (
                <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
                  {inc.status === "open" && (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleAction(inc.id, "investigating")}
                    >
                      🔍 Acknowledge
                    </button>
                  )}
                  <button
                    className="btn btn-sm"
                    style={{ background: "var(--status-up)", color: "white", border: "none" }}
                    onClick={() => handleAction(inc.id, "resolved")}
                  >
                    ✓ Resolve
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
