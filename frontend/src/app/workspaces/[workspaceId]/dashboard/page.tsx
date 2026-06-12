"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { Alert } from "@/components/ui/Alert";
import { IncidentSeverityBadge, IncidentStatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { PageSpinner } from "@/components/ui/Spinner";
import { ApiError, dashboardApi, incidentApi, workspaceApi } from "@/lib/api";
import { formatDateTime, formatMs, formatPercent } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace-context";

const STATUS_COLORS: Record<string, string> = {
  Up: "#16a34a",
  Down: "#dc2626",
  Pending: "#d97706",
};

export default function DashboardPage() {
  const workspace = useWorkspace();
  const queryClient = useQueryClient();

  const dashboardQuery = useQuery({
    queryKey: ["dashboard", workspace.id],
    queryFn: () => dashboardApi.get(workspace.id),
  });

  const incidentsQuery = useQuery({
    queryKey: ["incidents", workspace.id],
    queryFn: () => incidentApi.list(workspace.id),
  });

  const regenerateMutation = useMutation({
    mutationFn: () => workspaceApi.regenerateInviteCode(workspace.id),
    onSuccess: (updated) => {
      queryClient.setQueryData(["workspace", workspace.id], updated);
    },
  });

  if (dashboardQuery.isLoading) return <PageSpinner />;

  if (dashboardQuery.error || !dashboardQuery.data) {
    return (
      <Alert tone="error">
        {dashboardQuery.error instanceof ApiError ? dashboardQuery.error.message : "Failed to load dashboard."}
      </Alert>
    );
  }

  const dashboard = dashboardQuery.data;
  const statusData = [
    { name: "Up", value: dashboard.monitor_status_counts.up },
    { name: "Down", value: dashboard.monitor_status_counts.down },
    { name: "Pending", value: dashboard.monitor_status_counts.pending },
  ].filter((entry) => entry.value > 0);

  const openIncidents = (incidentsQuery.data ?? []).filter((incident) => incident.status !== "resolved").slice(0, 5);
  const openIncidentCount = dashboard.incident_status_counts.open + dashboard.incident_status_counts.investigating;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Dashboard</h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total monitors" value={String(dashboard.total_monitors)} />
        <StatCard label="Monitors down" value={String(dashboard.monitor_status_counts.down)} />
        <StatCard label="Open incidents" value={String(openIncidentCount)} />
        <StatCard label="Pass rate (24h)" value={formatPercent(dashboard.overall_check_pass_ratio)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Monitor status</CardTitle>
          </CardHeader>
          <CardContent>
            {statusData.length === 0 ? (
              <p className="text-sm text-slate-500">No monitors yet.</p>
            ) : (
              <div className="h-48 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={40} outerRadius={70} paddingAngle={2}>
                      {statusData.map((entry) => (
                        <Cell key={entry.name} fill={STATUS_COLORS[entry.name]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
            <p className="mt-4 text-sm text-slate-500">
              Avg response time (24h): <span className="font-medium text-slate-900">{formatMs(dashboard.avg_response_time_ms)}</span>
            </p>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Open incidents</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {openIncidents.length === 0 ? (
              <p className="px-4 py-4 text-sm text-slate-500">No open incidents. Everything looks healthy.</p>
            ) : (
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-2">Title</th>
                    <th className="px-4 py-2">Severity</th>
                    <th className="px-4 py-2">Status</th>
                    <th className="px-4 py-2">Opened</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {openIncidents.map((incident) => (
                    <tr key={incident.id}>
                      <td className="px-4 py-2 font-medium text-slate-900">
                        <Link href={`/workspaces/${workspace.id}/incidents/${incident.id}`} className="hover:underline">
                          {incident.title}
                        </Link>
                      </td>
                      <td className="px-4 py-2">
                        <IncidentSeverityBadge severity={incident.severity} />
                      </td>
                      <td className="px-4 py-2">
                        <IncidentStatusBadge status={incident.status} />
                      </td>
                      <td className="px-4 py-2 text-slate-500">{formatDateTime(incident.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </div>

      {workspace.invite_code && (
        <Card>
          <CardHeader>
            <CardTitle>Invite teammates</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-3">
            <code className="rounded bg-slate-100 px-3 py-1.5 text-sm">{workspace.invite_code}</code>
            <Button
              variant="outline"
              size="sm"
              isLoading={regenerateMutation.isPending}
              onClick={() => regenerateMutation.mutate()}
            >
              Regenerate
            </Button>
            <p className="text-sm text-slate-500">Share this code so teammates can join via &quot;Join a workspace&quot;.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent>
        <p className="text-xs font-medium uppercase text-slate-500">{label}</p>
        <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
      </CardContent>
    </Card>
  );
}
