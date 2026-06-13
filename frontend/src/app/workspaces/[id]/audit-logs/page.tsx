"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiSearchAuditLogs, type AuditLog } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

export default function AuditLogsPage() {
  const params = useParams();
  const wsId = params.id as string;

  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState("");
  const [entityFilter, setEntityFilter] = useState("");

  function loadLogs() {
    setLoading(true);
    const params: Record<string, string | number> = { limit: 100, offset: 0 };
    if (actionFilter) params.action = actionFilter;
    if (entityFilter) params.entity_type = entityFilter;
    apiSearchAuditLogs(wsId, params)
      .then(setLogs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadLogs();
  }, [wsId, actionFilter, entityFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  const actions = [...new Set(logs.map((l) => l.action))].sort();
  const entityTypes = [...new Set(logs.map((l) => l.entity_type))].sort();

  function renderJson(data: Record<string, unknown> | null) {
    if (!data) return <span className="text-muted">—</span>;
    return (
      <code className="font-mono text-xs" style={{ maxWidth: 200, display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {JSON.stringify(data)}
      </code>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Audit Log</h1>
          <p className="page-subtitle">Track all changes across your workspace</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3" style={{ marginBottom: 20, flexWrap: "wrap" }}>
        <select
          className="select-field"
          style={{ width: "auto", minWidth: 180 }}
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
        >
          <option value="">All actions</option>
          {actions.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
        <select
          className="select-field"
          style={{ width: "auto", minWidth: 180 }}
          value={entityFilter}
          onChange={(e) => setEntityFilter(e.target.value)}
        >
          <option value="">All entity types</option>
          {entityTypes.map((e) => (
            <option key={e} value={e}>{e}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[1, 2, 3, 4, 5].map((i) => <div key={i} className="skeleton" style={{ height: 40 }} />)}
        </div>
      ) : logs.length === 0 ? (
        <div className="glass-card empty-state">
          <div className="empty-state-icon">📋</div>
          <div className="empty-state-title">No audit log entries</div>
          <div className="empty-state-desc">
            Actions in this workspace will appear here.
          </div>
        </div>
      ) : (
        <div className="table-wrapper glass-card" style={{ padding: 0 }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Action</th>
                <th>Entity</th>
                <th>User</th>
                <th>Changes</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id}>
                  <td style={{ whiteSpace: "nowrap" }}>{formatDateTime(log.created_at)}</td>
                  <td>
                    <span className="badge badge-neutral">{log.action}</span>
                  </td>
                  <td>
                    <span className="text-xs">{log.entity_type}</span>
                  </td>
                  <td className="text-xs">{log.user_id ? log.user_id.slice(0, 8) + "…" : "system"}</td>
                  <td>{renderJson(log.new_values || log.old_values)}</td>
                  <td className="text-xs font-mono">{log.ip_address || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
