"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { IncidentSeverityBadge, IncidentStatusBadge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { PageSpinner } from "@/components/ui/Spinner";
import { ApiError, incidentApi, monitorApi } from "@/lib/api";
import type { IncidentStatus } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace-context";

const FILTERS: { label: string; value: IncidentStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Open", value: "open" },
  { label: "Investigating", value: "investigating" },
  { label: "Resolved", value: "resolved" },
];

export default function IncidentsPage() {
  const workspace = useWorkspace();
  const [filter, setFilter] = useState<IncidentStatus | "all">("all");

  const incidentsQuery = useQuery({
    queryKey: ["incidents", workspace.id],
    queryFn: () => incidentApi.list(workspace.id),
  });

  const monitorsQuery = useQuery({
    queryKey: ["monitors", workspace.id],
    queryFn: () => monitorApi.list(workspace.id),
  });

  const monitorNames = new Map((monitorsQuery.data ?? []).map((monitor) => [monitor.id, monitor.name]));

  const incidents = (incidentsQuery.data ?? []).filter((incident) => filter === "all" || incident.status === filter);

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Incidents</h1>

      <div className="mt-4 flex gap-2">
        {FILTERS.map((item) => (
          <button
            key={item.value}
            onClick={() => setFilter(item.value)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              filter === item.value ? "bg-blue-600 text-white" : "bg-white text-slate-600 hover:bg-slate-100"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {incidentsQuery.isLoading && <PageSpinner />}

      {incidentsQuery.error && (
        <Alert tone="error" className="mt-4">
          {incidentsQuery.error instanceof ApiError ? incidentsQuery.error.message : "Failed to load incidents."}
        </Alert>
      )}

      {incidentsQuery.data && incidents.length === 0 && (
        <Alert tone="info" className="mt-4">
          No incidents match this filter.
        </Alert>
      )}

      {incidents.length > 0 && (
        <Card className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2">Monitor</th>
                <th className="px-4 py-2">Severity</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Opened</th>
                <th className="px-4 py-2">Resolved</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {incidents.map((incident) => (
                <tr key={incident.id}>
                  <td className="px-4 py-3 font-medium text-slate-900">
                    <Link href={`/workspaces/${workspace.id}/incidents/${incident.id}`} className="hover:underline">
                      {incident.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {monitorNames.get(incident.monitor_id) ?? (
                      <Link
                        href={`/workspaces/${workspace.id}/monitors/${incident.monitor_id}`}
                        className="hover:underline"
                      >
                        View monitor
                      </Link>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <IncidentSeverityBadge severity={incident.severity} />
                  </td>
                  <td className="px-4 py-3">
                    <IncidentStatusBadge status={incident.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-500">{formatDateTime(incident.created_at)}</td>
                  <td className="px-4 py-3 text-slate-500">{formatDateTime(incident.resolved_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
