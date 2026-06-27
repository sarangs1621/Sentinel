"use client";

import { useState, type FormEvent } from "react";
import {
  apiCreateMonitor,
  apiUpdateMonitor,
  ApiError,
  type Monitor,
  type MonitorCreate,
  type MonitorUpdate,
} from "@/lib/api";
import { monitorTypeIcon } from "@/lib/utils";

const targetPlaceholder: Record<string, string> = {
  http: "https://example.com/health",
  tcp: "db.example.com:5432",
  ping: "1.1.1.1",
};

interface MonitorModalProps {
  wsId: string;
  monitor?: Monitor | null;
  onClose: () => void;
  onSaved: (monitor: Monitor) => void;
}

export default function MonitorModal({ wsId, monitor, onClose, onSaved }: MonitorModalProps) {
  const isEdit = !!monitor;
  const [form, setForm] = useState<MonitorCreate>({
    name: monitor?.name ?? "",
    monitor_type: monitor?.monitor_type ?? "http",
    target: monitor?.target ?? "",
    check_interval_seconds: monitor?.check_interval_seconds ?? 60,
    failure_threshold: monitor?.failure_threshold ?? 3,
    is_active: monitor?.is_active ?? true,
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      let saved: Monitor;
      if (isEdit && monitor) {
        const update: MonitorUpdate = {
          name: form.name,
          target: form.target,
          check_interval_seconds: form.check_interval_seconds,
          failure_threshold: form.failure_threshold,
          is_active: form.is_active,
        };
        saved = await apiUpdateMonitor(wsId, monitor.id, update);
      } else {
        saved = await apiCreateMonitor(wsId, form);
      }
      onSaved(saved);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail : `Failed to ${isEdit ? "update" : "create"} monitor`
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{isEdit ? "Edit monitor" : "Create monitor"}</h2>
          <button className="btn btn-ghost btn-icon" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {error && <div className="auth-error">{error}</div>}
            <div>
              <label className="input-label" htmlFor="monitor-name">Name *</label>
              <input
                id="monitor-name"
                className="input-field"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
                placeholder="Production API"
                autoFocus
              />
            </div>
            <div>
              <label className="input-label" htmlFor="monitor-type">Type *</label>
              {isEdit ? (
                <input
                  className="input-field"
                  disabled
                  value={`${monitorTypeIcon(form.monitor_type)} ${form.monitor_type.toUpperCase()}`}
                />
              ) : (
                <select
                  id="monitor-type"
                  className="select-field"
                  value={form.monitor_type}
                  onChange={(e) => setForm({ ...form, monitor_type: e.target.value as MonitorCreate["monitor_type"] })}
                >
                  <option value="http">🌐 HTTP</option>
                  <option value="tcp">🔌 TCP</option>
                  <option value="ping">📡 PING</option>
                </select>
              )}
            </div>
            <div>
              <label className="input-label" htmlFor="monitor-target">Target *</label>
              <input
                id="monitor-target"
                className="input-field"
                value={form.target}
                onChange={(e) => setForm({ ...form, target: e.target.value })}
                required
                placeholder={targetPlaceholder[form.monitor_type]}
              />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <label className="input-label" htmlFor="monitor-interval">Check interval (s)</label>
                <input
                  id="monitor-interval"
                  type="number"
                  className="input-field"
                  value={form.check_interval_seconds}
                  onChange={(e) => setForm({ ...form, check_interval_seconds: Number(e.target.value) })}
                  min={30}
                  max={86400}
                />
              </div>
              <div>
                <label className="input-label" htmlFor="monitor-threshold">Failure threshold</label>
                <input
                  id="monitor-threshold"
                  type="number"
                  className="input-field"
                  value={form.failure_threshold}
                  onChange={(e) => setForm({ ...form, failure_threshold: Number(e.target.value) })}
                  min={1}
                  max={100}
                />
              </div>
            </div>
            {isEdit && (
              <label className="flex items-center gap-2" style={{ cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                  style={{ width: 16, height: 16, accentColor: "var(--accent-primary)" }}
                />
                <span className="text-sm">Monitor active (uncheck to pause checks)</span>
              </label>
            )}
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? (isEdit ? "Saving…" : "Creating…") : isEdit ? "Save changes" : "Create monitor"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
