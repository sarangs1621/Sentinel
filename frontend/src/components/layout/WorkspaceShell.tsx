"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode } from "react";

import { WorkspaceRoleBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth-context";
import type { Workspace } from "@/lib/types";

interface WorkspaceShellProps {
  workspace: Workspace;
  children: ReactNode;
}

function navItems(workspaceId: string) {
  return [
    { href: `/workspaces/${workspaceId}/dashboard`, label: "Dashboard" },
    { href: `/workspaces/${workspaceId}/monitors`, label: "Monitors" },
    { href: `/workspaces/${workspaceId}/incidents`, label: "Incidents" },
  ];
}

export function WorkspaceShell({ workspace, children }: WorkspaceShellProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <Link href="/workspaces" className="text-lg font-semibold text-slate-900">
            Sentinel
          </Link>
          <span className="text-slate-300">/</span>
          <span className="font-medium text-slate-700">{workspace.name}</span>
          <WorkspaceRoleBadge role={workspace.role} />
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden text-sm text-slate-500 sm:inline">{user?.email}</span>
          <Button variant="ghost" size="sm" onClick={() => void logout()}>
            Log out
          </Button>
        </div>
      </header>
      <div className="flex flex-1 flex-col sm:flex-row">
        <nav className="flex gap-1 border-b border-slate-200 bg-white px-4 py-2 sm:w-48 sm:flex-col sm:border-b-0 sm:border-r sm:px-3 sm:py-4">
          {navItems(workspace.id).map((item) => {
            const isActive = pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <main className="flex-1 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
