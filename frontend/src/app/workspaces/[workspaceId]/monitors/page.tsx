"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { MonitorStatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageSpinner } from "@/components/ui/Spinner";
import { ApiError, monitorApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canManageMonitor, formatRelativeTime } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace-context";

export default function MonitorsPage() {
  const workspace = useWorkspace();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const {
    data: monitors,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["monitors", workspace.id],
    queryFn: () => monitorApi.list(workspace.id),
  });

  const deleteMutation = useMutation({
    mutationFn: (monitorId: string) => monitorApi.remove(workspace.id, monitorId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["monitors", workspace.id] }),
    onError: (err) => setDeleteError(err instanceof ApiError ? err.message : "Failed to delete monitor."),
  });

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Monitors</h1>
        <Link href={`/workspaces/${workspace.id}/monitors/new`}>
          <Button>New monitor</Button>
        </Link>
      </div>

      {isLoading && <PageSpinner />}

      {error && (
        <Alert tone="error" className="mt-4">
          {error instanceof ApiError ? error.message : "Failed to load monitors."}
        </Alert>
      )}

      {deleteError && (
        <Alert tone="error" className="mt-4">
          {deleteError}
        </Alert>
      )}

      {monitors?.length === 0 && (
        <Alert tone="info" className="mt-4">
          No monitors yet. Create one to start tracking uptime.
        </Alert>
      )}

      {monitors && monitors.length > 0 && (
        <Card className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Type</th>
                <th className="px-4 py-2">Target</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Failures</th>
                <th className="px-4 py-2">Last checked</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {monitors.map((monitor) => (
                <tr key={monitor.id}>
                  <td className="px-4 py-3 font-medium text-slate-900">
                    <Link href={`/workspaces/${workspace.id}/monitors/${monitor.id}`} className="hover:underline">
                      {monitor.name}
                    </Link>
                    {!monitor.is_active && <span className="ml-2 text-xs text-slate-400">(paused)</span>}
                  </td>
                  <td className="px-4 py-3 uppercase text-slate-500">{monitor.monitor_type}</td>
                  <td className="max-w-xs truncate px-4 py-3 text-slate-500">{monitor.target}</td>
                  <td className="px-4 py-3">
                    <MonitorStatusBadge status={monitor.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {monitor.consecutive_failures}/{monitor.failure_threshold}
                  </td>
                  <td className="px-4 py-3 text-slate-500">{formatRelativeTime(monitor.last_checked_at)}</td>
                  <td className="px-4 py-3 text-right">
                    {canManageMonitor(workspace, monitor, user?.id) && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (window.confirm(`Delete monitor "${monitor.name}"?`)) {
                            setDeleteError(null);
                            deleteMutation.mutate(monitor.id);
                          }
                        }}
                      >
                        Delete
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
