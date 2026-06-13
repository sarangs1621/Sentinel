"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  apiListWorkspaces,
  apiCreateWorkspace,
  apiJoinWorkspace,
  ApiError,
  type Workspace,
} from "@/lib/api";
import { formatRelative } from "@/lib/utils";

export default function WorkspacesPage() {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showJoin, setShowJoin] = useState(false);
  const [error, setError] = useState("");

  // Create form
  const [cName, setCName] = useState("");
  const [cDesc, setCDesc] = useState("");
  const [cSlug, setCSlug] = useState("");
  const [cLoading, setCLoading] = useState(false);

  // Join form
  const [jCode, setJCode] = useState("");
  const [jLoading, setJLoading] = useState(false);

  useEffect(() => {
    apiListWorkspaces()
      .then(setWorkspaces)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    setCLoading(true);
    try {
      const ws = await apiCreateWorkspace({
        name: cName,
        description: cDesc || undefined,
        slug: cSlug || undefined,
      });
      router.push(`/workspaces/${ws.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to create workspace");
    } finally {
      setCLoading(false);
    }
  }

  async function handleJoin(e: FormEvent) {
    e.preventDefault();
    setError("");
    setJLoading(true);
    try {
      const ws = await apiJoinWorkspace(jCode);
      router.push(`/workspaces/${ws.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to join workspace");
    } finally {
      setJLoading(false);
    }
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Workspaces</h1>
          <p className="page-subtitle">Select a workspace to manage your monitors</p>
        </div>
        <div className="flex gap-3">
          <button className="btn btn-secondary" onClick={() => { setShowJoin(true); setShowCreate(false); }}>
            Join workspace
          </button>
          <button className="btn btn-primary" onClick={() => { setShowCreate(true); setShowJoin(false); }}>
            + Create workspace
          </button>
        </div>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create workspace</h2>
              <button className="btn btn-ghost btn-icon" onClick={() => setShowCreate(false)}>✕</button>
            </div>
            <form onSubmit={handleCreate}>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {error && <div className="auth-error">{error}</div>}
                <div>
                  <label className="input-label" htmlFor="create-ws-name">Name *</label>
                  <input id="create-ws-name" className="input-field" value={cName} onChange={(e) => setCName(e.target.value)} required placeholder="My Team" autoFocus />
                </div>
                <div>
                  <label className="input-label" htmlFor="create-ws-slug">Slug (optional)</label>
                  <input id="create-ws-slug" className="input-field" value={cSlug} onChange={(e) => setCSlug(e.target.value)} placeholder="my-team" />
                </div>
                <div>
                  <label className="input-label" htmlFor="create-ws-desc">Description</label>
                  <textarea id="create-ws-desc" className="input-field" value={cDesc} onChange={(e) => setCDesc(e.target.value)} placeholder="What is this workspace for?" rows={3} style={{ resize: "vertical" }} />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowCreate(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={cLoading}>
                  {cLoading ? "Creating…" : "Create workspace"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Join Modal */}
      {showJoin && (
        <div className="modal-overlay" onClick={() => setShowJoin(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Join workspace</h2>
              <button className="btn btn-ghost btn-icon" onClick={() => setShowJoin(false)}>✕</button>
            </div>
            <form onSubmit={handleJoin}>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {error && <div className="auth-error">{error}</div>}
                <div>
                  <label className="input-label" htmlFor="join-code">Invite code *</label>
                  <input id="join-code" className="input-field" value={jCode} onChange={(e) => setJCode(e.target.value)} required placeholder="Paste invite code here" autoFocus />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowJoin(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={jLoading}>
                  {jLoading ? "Joining…" : "Join"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Workspace Grid */}
      {loading ? (
        <div className="workspace-grid">
          {[1, 2, 3].map((i) => (
            <div key={i} className="glass-card skeleton skeleton-card" style={{ height: 160 }} />
          ))}
        </div>
      ) : workspaces.length === 0 ? (
        <div className="empty-state glass-card" style={{ marginTop: 32 }}>
          <div className="empty-state-icon">🏢</div>
          <div className="empty-state-title">No workspaces yet</div>
          <div className="empty-state-desc">
            Create your first workspace to start monitoring your services, or join an existing one with an invite code.
          </div>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            + Create workspace
          </button>
        </div>
      ) : (
        <div className="workspace-grid stagger-children">
          {workspaces.map((ws) => (
            <div
              key={ws.id}
              className="glass-card workspace-card"
              onClick={() => router.push(`/workspaces/${ws.id}`)}
            >
              <div className="workspace-card-header">
                <div className="workspace-card-icon">
                  {ws.name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <div className="workspace-card-name">{ws.name}</div>
                  <div className="workspace-card-slug">/{ws.slug}</div>
                </div>
              </div>
              {ws.description && (
                <div className="workspace-card-desc">{ws.description}</div>
              )}
              <div className="workspace-card-meta">
                <span className={`badge badge-neutral`}>{ws.role}</span>
                <span>Created {formatRelative(ws.created_at)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
