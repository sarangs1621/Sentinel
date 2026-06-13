"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  apiGetWorkspace,
  apiUpdateWorkspace,
  apiRegenerateInviteCode,
  apiDeleteWorkspace,
  apiListMembers,
  apiUpdateMemberRole,
  apiRemoveMember,
  apiLeaveWorkspace,
  apiListApiKeys,
  apiCreateApiKey,
  apiRevokeApiKey,
  ApiError,
  type Workspace,
  type WorkspaceMember,
  type ApiKey,
} from "@/lib/api";
import { formatRelative, formatDateTime, getInitials } from "@/lib/utils";

export default function SettingsPage() {
  const params = useParams();
  const router = useRouter();
  const wsId = params.id as string;

  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [tab, setTab] = useState<"general" | "members" | "api-keys">("general");

  // Edit form
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [saving, setSaving] = useState(false);

  // API keys
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [apiKeysLoading, setApiKeysLoading] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [creatingKey, setCreatingKey] = useState(false);
  const [newKeySecret, setNewKeySecret] = useState<string | null>(null);

  function loadData() {
    Promise.all([apiGetWorkspace(wsId), apiListMembers(wsId)])
      .then(([ws, m]) => {
        setWorkspace(ws);
        setMembers(m);
        setEditName(ws.name);
        setEditDesc(ws.description || "");
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadData();
  }, [wsId]); // eslint-disable-line react-hooks/exhaustive-deps

  function loadApiKeys() {
    setApiKeysLoading(true);
    apiListApiKeys(wsId)
      .then(setApiKeys)
      .catch(() => {})
      .finally(() => setApiKeysLoading(false));
  }

  useEffect(() => {
    if (tab === "api-keys") {
      loadApiKeys();
    }
  }, [tab]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSaving(true);
    try {
      const ws = await apiUpdateWorkspace(wsId, { name: editName, description: editDesc || undefined });
      setWorkspace(ws);
      setSuccess("Workspace updated successfully");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to update workspace");
    } finally {
      setSaving(false);
    }
  }

  async function handleRegenInvite() {
    if (!confirm("Regenerate invite code? The old code will stop working.")) return;
    try {
      const ws = await apiRegenerateInviteCode(wsId);
      setWorkspace(ws);
      setSuccess("Invite code regenerated");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to regenerate invite code");
    }
  }

  async function handleDeleteWorkspace() {
    if (!confirm("Delete this workspace? This action is permanent and cannot be undone.")) return;
    try {
      await apiDeleteWorkspace(wsId);
      router.push("/workspaces");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to delete workspace");
    }
  }

  async function handleLeaveWorkspace() {
    if (!confirm("Leave this workspace? You will lose access unless re-invited.")) return;
    try {
      await apiLeaveWorkspace(wsId);
      router.push("/workspaces");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to leave workspace");
    }
  }

  async function handleRoleChange(userId: string, newRole: string) {
    try {
      await apiUpdateMemberRole(wsId, userId, newRole);
      loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to update role");
    }
  }

  async function handleRemoveMember(userId: string) {
    if (!confirm("Remove this member from the workspace?")) return;
    try {
      await apiRemoveMember(wsId, userId);
      loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to remove member");
    }
  }

  async function handleCreateApiKey(e: FormEvent) {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    setError("");
    setCreatingKey(true);
    try {
      const created = await apiCreateApiKey(wsId, newKeyName.trim());
      setNewKeySecret(created.api_key);
      setNewKeyName("");
      loadApiKeys();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to create API key");
    } finally {
      setCreatingKey(false);
    }
  }

  async function handleRevokeApiKey(keyId: string) {
    if (!confirm("Revoke this API key? Any integration using it will stop working immediately.")) return;
    try {
      await apiRevokeApiKey(wsId, keyId);
      loadApiKeys();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to revoke API key");
    }
  }

  if (loading) {
    return (
      <div>
        <h1 className="page-title">Settings</h1>
        <div className="glass-card skeleton" style={{ height: 300, marginTop: 20 }} />
      </div>
    );
  }

  const isOwnerOrAdmin = workspace?.role === "owner" || workspace?.role === "admin";

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
      </div>

      {error && <div className="auth-error" style={{ marginBottom: 16 }}>{error}</div>}
      {success && (
        <div style={{ padding: "12px 16px", background: "var(--status-up-bg)", border: "1px solid var(--status-up-border)", borderRadius: "var(--radius-md)", color: "var(--status-up)", fontSize: "0.8125rem", marginBottom: 16 }}>
          {success}
        </div>
      )}

      {/* Tabs */}
      <div className="tabs">
        <button className={`tab ${tab === "general" ? "active" : ""}`} onClick={() => setTab("general")}>General</button>
        <button className={`tab ${tab === "members" ? "active" : ""}`} onClick={() => setTab("members")}>
          Members <span style={{ marginLeft: 4, opacity: 0.6, fontSize: "0.75rem" }}>{members.length}</span>
        </button>
        {isOwnerOrAdmin && (
          <button className={`tab ${tab === "api-keys" ? "active" : ""}`} onClick={() => setTab("api-keys")}>
            API Keys
          </button>
        )}
      </div>

      {tab === "general" && (
        <div style={{ maxWidth: 600 }}>
          <form onSubmit={handleSave} className="glass-card" style={{ padding: 24 }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 20 }}>Workspace details</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <label className="input-label" htmlFor="ws-name">Name</label>
                <input id="ws-name" className="input-field" value={editName} onChange={(e) => setEditName(e.target.value)} required disabled={!isOwnerOrAdmin} />
              </div>
              <div>
                <label className="input-label" htmlFor="ws-desc">Description</label>
                <textarea id="ws-desc" className="input-field" value={editDesc} onChange={(e) => setEditDesc(e.target.value)} rows={3} disabled={!isOwnerOrAdmin} style={{ resize: "vertical" }} />
              </div>
              {isOwnerOrAdmin && (
                <button type="submit" className="btn btn-primary" disabled={saving} style={{ alignSelf: "flex-start" }}>
                  {saving ? "Saving…" : "Save changes"}
                </button>
              )}
            </div>
          </form>

          {/* Invite Code */}
          {workspace?.invite_code && (
            <div className="glass-card" style={{ padding: 24, marginTop: 16 }}>
              <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 12 }}>Invite code</h3>
              <div className="flex items-center gap-3">
                <code className="input-field font-mono" style={{ flex: 1, cursor: "pointer", background: "var(--bg-tertiary)" }} onClick={() => { navigator.clipboard.writeText(workspace.invite_code!); setSuccess("Copied!"); }}>
                  {workspace.invite_code}
                </code>
                {isOwnerOrAdmin && (
                  <button className="btn btn-secondary btn-sm" onClick={handleRegenInvite}>Regenerate</button>
                )}
              </div>
              <p className="text-xs text-muted" style={{ marginTop: 8 }}>Share this code with team members to let them join. Click to copy.</p>
            </div>
          )}

          {/* Danger Zone */}
          {workspace?.role === "owner" ? (
            <div className="glass-card" style={{ padding: 24, marginTop: 16, borderColor: "var(--status-down-border)" }}>
              <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--status-down)", marginBottom: 12 }}>Danger zone</h3>
              <p className="text-sm text-muted" style={{ marginBottom: 16 }}>
                Permanently delete this workspace and all its data, including monitors, incidents, and alert rules.
              </p>
              <button className="btn btn-danger btn-sm" onClick={handleDeleteWorkspace}>
                Delete workspace
              </button>
            </div>
          ) : (
            <div className="glass-card" style={{ padding: 24, marginTop: 16, borderColor: "var(--status-down-border)" }}>
              <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--status-down)", marginBottom: 12 }}>Danger zone</h3>
              <p className="text-sm text-muted" style={{ marginBottom: 16 }}>
                Remove yourself from this workspace. You will lose access to its monitors, incidents, and settings.
              </p>
              <button className="btn btn-danger btn-sm" onClick={handleLeaveWorkspace}>
                Leave workspace
              </button>
            </div>
          )}
        </div>
      )}

      {tab === "members" && (
        <div className="table-wrapper glass-card" style={{ padding: 0, maxWidth: 800 }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Member</th>
                <th>Role</th>
                <th>Joined</th>
                {isOwnerOrAdmin && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.user_id}>
                  <td>
                    <div className="flex items-center gap-3">
                      <div className="sidebar-user-avatar" style={{ width: 28, height: 28, fontSize: "0.6875rem" }}>
                        {getInitials(m.full_name || m.email)}
                      </div>
                      <div>
                        <div style={{ fontWeight: 500, color: "var(--text-primary)", fontSize: "0.8125rem" }}>
                          {m.full_name || "Unnamed"}
                        </div>
                        <div className="text-xs text-muted">{m.email}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    {isOwnerOrAdmin && m.role !== "owner" ? (
                      <select className="select-field" style={{ width: "auto", padding: "4px 28px 4px 8px", fontSize: "0.75rem" }} value={m.role} onChange={(e) => handleRoleChange(m.user_id, e.target.value)}>
                        <option value="member">member</option>
                        <option value="admin">admin</option>
                      </select>
                    ) : (
                      <span className="badge badge-neutral">{m.role}</span>
                    )}
                  </td>
                  <td className="text-xs">{formatRelative(m.created_at)}</td>
                  {isOwnerOrAdmin && (
                    <td>
                      {m.role !== "owner" && (
                        <button className="btn btn-ghost btn-sm" style={{ color: "var(--status-down)" }} onClick={() => handleRemoveMember(m.user_id)}>
                          Remove
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "api-keys" && (
        <div style={{ maxWidth: 700 }}>
          {newKeySecret && (
            <div className="glass-card" style={{ padding: 20, marginBottom: 16, borderColor: "var(--accent-primary)" }}>
              <h3 style={{ fontSize: "0.9375rem", fontWeight: 600, marginBottom: 8 }}>API key created</h3>
              <p className="text-sm text-muted" style={{ marginBottom: 12 }}>
                Copy this key now — for security reasons, you won&apos;t be able to see it again.
              </p>
              <div className="flex items-center gap-3">
                <code
                  className="input-field font-mono"
                  style={{ flex: 1, cursor: "pointer", background: "var(--bg-tertiary)", wordBreak: "break-all" }}
                  onClick={() => { navigator.clipboard.writeText(newKeySecret); setSuccess("Copied!"); }}
                >
                  {newKeySecret}
                </code>
                <button className="btn btn-secondary btn-sm" onClick={() => setNewKeySecret(null)}>Done</button>
              </div>
            </div>
          )}

          <form onSubmit={handleCreateApiKey} className="glass-card" style={{ padding: 24, marginBottom: 16 }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 16 }}>Create API key</h3>
            <div className="flex items-end gap-3">
              <div style={{ flex: 1 }}>
                <label className="input-label" htmlFor="key-name">Name</label>
                <input
                  id="key-name"
                  className="input-field"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  placeholder="CI pipeline"
                  required
                />
              </div>
              <button type="submit" className="btn btn-primary" disabled={creatingKey}>
                {creatingKey ? "Creating…" : "+ Create key"}
              </button>
            </div>
          </form>

          {apiKeysLoading ? (
            <div className="glass-card skeleton" style={{ height: 120 }} />
          ) : apiKeys.length === 0 ? (
            <div className="glass-card empty-state">
              <div className="empty-state-icon">🔑</div>
              <div className="empty-state-title">No API keys</div>
              <div className="empty-state-desc">
                Create an API key to authenticate external integrations with this workspace.
              </div>
            </div>
          ) : (
            <div className="table-wrapper glass-card" style={{ padding: 0 }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Key</th>
                    <th>Created</th>
                    <th>Last used</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {apiKeys.map((k) => (
                    <tr key={k.id}>
                      <td style={{ fontWeight: 500 }}>{k.name}</td>
                      <td className="font-mono text-xs">{k.key_prefix}…</td>
                      <td className="text-xs">{formatDateTime(k.created_at)}</td>
                      <td className="text-xs">{k.last_used_at ? formatRelative(k.last_used_at) : "Never"}</td>
                      <td>
                        {k.revoked_at ? (
                          <span className="badge badge-neutral">Revoked</span>
                        ) : (
                          <span className="badge badge-up">Active</span>
                        )}
                      </td>
                      <td>
                        {!k.revoked_at && (
                          <button className="btn btn-ghost btn-sm" style={{ color: "var(--status-down)" }} onClick={() => handleRevokeApiKey(k.id)}>
                            Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
