"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, usePathname, useParams } from "next/navigation";
import Link from "next/link";
import { apiGetMe, apiLogout, apiGetWorkspace, type User, type Workspace } from "@/lib/api";
import { getInitials } from "@/lib/utils";

export default function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams();
  const workspaceId = params?.id as string | undefined;

  const [user, setUser] = useState<User | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    apiGetMe()
      .then(setUser)
      .catch(() => {
        router.replace("/login");
      })
      .finally(() => setLoading(false));
  }, [router]);

  useEffect(() => {
    if (workspaceId) {
      apiGetWorkspace(workspaceId)
        .then(setWorkspace)
        .catch(() => {});
    }
  }, [workspaceId]);

  const handleLogout = useCallback(async () => {
    await apiLogout();
    router.push("/login");
  }, [router]);

  if (loading) {
    return (
      <div className="loading-page" style={{ minHeight: "100vh" }}>
        <div className="spinner spinner-lg" />
        <p className="loading-page-text">Loading…</p>
      </div>
    );
  }

  const isWorkspacePage = !!workspaceId;

  const navItems = isWorkspacePage
    ? [
        { label: "Dashboard", href: `/workspaces/${workspaceId}`, icon: "📊", exact: true },
        { label: "Monitors", href: `/workspaces/${workspaceId}/monitors`, icon: "🖥️" },
        { label: "Incidents", href: `/workspaces/${workspaceId}/incidents`, icon: "🔔" },
        { label: "Alert Rules", href: `/workspaces/${workspaceId}/alerts`, icon: "⚡" },
        { label: "Notifications", href: `/workspaces/${workspaceId}/notifications`, icon: "📨" },
        { label: "Audit Log", href: `/workspaces/${workspaceId}/audit-logs`, icon: "📋" },
        { label: "Settings", href: `/workspaces/${workspaceId}/settings`, icon: "⚙️" },
      ]
    : [];

  function isActive(href: string, exact?: boolean) {
    if (exact) return pathname === href;
    return pathname.startsWith(href);
  }

  return (
    <div className="app-layout">
      {/* Mobile toggle */}
      <button
        className="sidebar-mobile-toggle"
        onClick={() => setSidebarOpen(!sidebarOpen)}
        aria-label="Toggle menu"
      >
        ☰
      </button>

      {/* Backdrop */}
      <div
        className={`sidebar-backdrop ${sidebarOpen ? "visible" : ""}`}
        onClick={() => setSidebarOpen(false)}
      />

      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">S</div>
          <span className="sidebar-logo-text">Sentinel</span>
        </div>

        <nav className="sidebar-nav">
          {/* Workspaces link */}
          <Link
            href="/workspaces"
            className={`sidebar-link ${pathname === "/workspaces" ? "active" : ""}`}
            onClick={() => setSidebarOpen(false)}
          >
            <span className="link-icon">🏢</span>
            Workspaces
          </Link>

          {/* Workspace nav items */}
          {isWorkspacePage && workspace && (
            <>
              <div className="sidebar-section-label">
                {workspace.name}
              </div>
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`sidebar-link ${isActive(item.href, item.exact) ? "active" : ""}`}
                  onClick={() => setSidebarOpen(false)}
                >
                  <span className="link-icon">{item.icon}</span>
                  {item.label}
                </Link>
              ))}
            </>
          )}
        </nav>

        {/* User footer */}
        <div className="sidebar-footer">
          <div className="sidebar-user" onClick={handleLogout} title="Sign out">
            <div className="sidebar-user-avatar">
              {getInitials(user?.full_name || user?.email)}
            </div>
            <div className="sidebar-user-info">
              <div className="sidebar-user-name">
                {user?.full_name || "User"}
              </div>
              <div className="sidebar-user-email">{user?.email}</div>
            </div>
            <span style={{ fontSize: "1.1rem", opacity: 0.5 }}>↗</span>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="main-content">
        <div className="main-content-inner">{children}</div>
      </main>
    </div>
  );
}
