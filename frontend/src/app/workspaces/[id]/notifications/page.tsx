"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  apiListNotifications,
  apiListIncidents,
  apiListAlertRules,
  type Notification,
  type Incident,
  type AlertRule,
} from "@/lib/api";
import { formatDateTime, statusBadgeClass, channelTypeIcon } from "@/lib/utils";

const eventLabels: Record<string, string> = {
  incident_opened: "Incident opened",
  incident_resolved: "Incident resolved",
};

export default function NotificationsPage() {
  const params = useParams();
  const wsId = params.id as string;

  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [alertRules, setAlertRules] = useState<AlertRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    Promise.all([apiListNotifications(wsId), apiListIncidents(wsId), apiListAlertRules(wsId)])
      .then(([n, i, r]) => {
        setNotifications(n);
        setIncidents(i);
        setAlertRules(r);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [wsId]);

  const incidentMap = new Map(incidents.map((i) => [i.id, i]));
  const ruleMap = new Map(alertRules.map((r) => [r.id, r]));

  const filtered = statusFilter ? notifications.filter((n) => n.status === statusFilter) : notifications;
  const sorted = [...filtered].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Notifications</h1>
          <p className="page-subtitle">Alert delivery log for this workspace</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3" style={{ marginBottom: 20, flexWrap: "wrap" }}>
        <select
          className="select-field"
          style={{ width: "auto", minWidth: 160 }}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="sent">Sent</option>
          <option value="failed">Failed</option>
          <option value="pending">Pending</option>
        </select>
      </div>

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[1, 2, 3, 4].map((i) => <div key={i} className="skeleton" style={{ height: 48 }} />)}
        </div>
      ) : sorted.length === 0 ? (
        <div className="glass-card empty-state">
          <div className="empty-state-icon">📨</div>
          <div className="empty-state-title">No notifications yet</div>
          <div className="empty-state-desc">
            Alert delivery attempts for incidents will appear here once an alert rule fires.
          </div>
        </div>
      ) : (
        <div className="table-wrapper glass-card" style={{ padding: 0 }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Event</th>
                <th>Incident</th>
                <th>Channel</th>
                <th>Status</th>
                <th>Attempts</th>
                <th>Response</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((n) => {
                const incident = incidentMap.get(n.incident_id);
                const rule = ruleMap.get(n.alert_rule_id);
                return (
                  <tr key={n.id}>
                    <td style={{ whiteSpace: "nowrap" }}>{formatDateTime(n.created_at)}</td>
                    <td className="text-xs">{eventLabels[n.event_type] || n.event_type}</td>
                    <td className="truncate" style={{ maxWidth: 200 }}>
                      {incident?.title || `${n.incident_id.slice(0, 8)}…`}
                    </td>
                    <td>
                      {rule ? (
                        <span className="flex items-center gap-2">
                          {channelTypeIcon(rule.channel_type)}
                          <span className="text-xs">{rule.name}</span>
                        </span>
                      ) : (
                        <span className="text-xs text-muted">{n.alert_rule_id.slice(0, 8)}…</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${statusBadgeClass(n.status)}`}>{n.status}</span>
                    </td>
                    <td className="text-xs">{n.attempts}</td>
                    <td className="text-xs">{n.response_status_code ?? "—"}</td>
                    <td className="truncate text-xs" style={{ maxWidth: 240 }}>{n.error_message || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
