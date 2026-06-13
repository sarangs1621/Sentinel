"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "next/navigation";
import {
  apiListAlertRules,
  apiCreateAlertRule,
  apiUpdateAlertRule,
  apiDeleteAlertRule,
  ApiError,
  type AlertRule,
  type AlertRuleCreate,
} from "@/lib/api";
import { formatRelative, channelTypeIcon } from "@/lib/utils";

export default function AlertRulesPage() {
  const params = useParams();
  const wsId = params.id as string;

  const [rules, setRules] = useState<AlertRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState("");
  const [createLoading, setCreateLoading] = useState(false);

  const [form, setForm] = useState<AlertRuleCreate>({
    name: "",
    channel_type: "webhook",
    target: "",
    is_enabled: true,
    min_severity: null,
  });

  function loadRules() {
    apiListAlertRules(wsId)
      .then(setRules)
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadRules();
  }, [wsId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    setCreateLoading(true);
    try {
      await apiCreateAlertRule(wsId, form);
      setShowCreate(false);
      setForm({ name: "", channel_type: "webhook", target: "", is_enabled: true, min_severity: null });
      loadRules();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to create alert rule");
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleToggle(rule: AlertRule) {
    try {
      await apiUpdateAlertRule(wsId, rule.id, { is_enabled: !rule.is_enabled });
      loadRules();
    } catch { /* ignore */ }
  }

  async function handleDelete(ruleId: string) {
    if (!confirm("Delete this alert rule?")) return;
    try {
      await apiDeleteAlertRule(wsId, ruleId);
      loadRules();
    } catch { /* ignore */ }
  }

  const targetPlaceholder: Record<string, string> = {
    webhook: "https://hooks.slack.com/services/...",
    email: "alerts@example.com",
  };

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Alert Rules</h1>
          <p className="page-subtitle">Configure how you get notified about incidents</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          + New alert rule
        </button>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create alert rule</h2>
              <button className="btn btn-ghost btn-icon" onClick={() => setShowCreate(false)}>✕</button>
            </div>
            <form onSubmit={handleCreate}>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {error && <div className="auth-error">{error}</div>}
                <div>
                  <label className="input-label" htmlFor="rule-name">Name *</label>
                  <input id="rule-name" className="input-field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required placeholder="Slack production alerts" autoFocus />
                </div>
                <div>
                  <label className="input-label" htmlFor="rule-channel">Channel type *</label>
                  <select id="rule-channel" className="select-field" value={form.channel_type} onChange={(e) => setForm({ ...form, channel_type: e.target.value as "webhook" | "email" })}>
                    <option value="webhook">🔗 Webhook</option>
                    <option value="email">📧 Email</option>
                  </select>
                </div>
                <div>
                  <label className="input-label" htmlFor="rule-target">Target *</label>
                  <input id="rule-target" className="input-field" value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} required placeholder={targetPlaceholder[form.channel_type]} />
                </div>
                <div>
                  <label className="input-label" htmlFor="rule-severity">Minimum severity</label>
                  <select id="rule-severity" className="select-field" value={form.min_severity ?? ""} onChange={(e) => setForm({ ...form, min_severity: e.target.value || null })}>
                    <option value="">Any severity</option>
                    <option value="minor">Minor</option>
                    <option value="major">Major</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowCreate(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={createLoading}>
                  {createLoading ? "Creating…" : "Create rule"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Rules List */}
      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {[1, 2].map((i) => <div key={i} className="glass-card skeleton" style={{ height: 72 }} />)}
        </div>
      ) : rules.length === 0 ? (
        <div className="glass-card empty-state">
          <div className="empty-state-icon">⚡</div>
          <div className="empty-state-title">No alert rules</div>
          <div className="empty-state-desc">
            Create alert rules to get notified via webhook or email when incidents occur.
          </div>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            + New alert rule
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }} className="stagger-children">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className="glass-card"
              style={{ padding: "16px 20px", display: "flex", alignItems: "center", gap: 16, opacity: rule.is_enabled ? 1 : 0.6 }}
            >
              <div style={{ fontSize: "1.5rem" }}>{channelTypeIcon(rule.channel_type)}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>{rule.name}</div>
                <div className="text-xs text-muted font-mono truncate">{rule.target}</div>
                <div className="text-xs text-muted" style={{ marginTop: 4 }}>
                  {rule.min_severity ? `≥ ${rule.min_severity}` : "All severities"} · {formatRelative(rule.created_at)}
                </div>
              </div>
              <div className="flex items-center gap-2" style={{ flexShrink: 0 }}>
                <button
                  className={`btn btn-sm ${rule.is_enabled ? "btn-secondary" : "btn-primary"}`}
                  onClick={() => handleToggle(rule)}
                >
                  {rule.is_enabled ? "Disable" : "Enable"}
                </button>
                <button
                  className="btn btn-ghost btn-icon btn-sm"
                  onClick={() => handleDelete(rule.id)}
                  title="Delete"
                >
                  🗑
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
