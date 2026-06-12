"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { IncidentSeverityBadge, IncidentStatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { PageSpinner } from "@/components/ui/Spinner";
import { ApiError, incidentApi, monitorApi } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace-context";

export default function IncidentDetailPage() {
  const workspace = useWorkspace();
  const params = useParams<{ incidentId: string }>();
  const incidentId = params.incidentId;
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);

  const incidentQuery = useQuery({
    queryKey: ["incident", workspace.id, incidentId],
    queryFn: () => incidentApi.get(workspace.id, incidentId),
  });

  const incident = incidentQuery.data;
  const monitorId = incident?.monitor_id;

  const monitorQuery = useQuery({
    queryKey: ["monitor", workspace.id, monitorId],
    queryFn: () => monitorApi.get(workspace.id, monitorId as string),
    enabled: !!monitorId,
  });

  const updateMutation = useMutation({
    mutationFn: (status: "investigating" | "resolved") => incidentApi.update(workspace.id, incidentId, status),
    onSuccess: async (updated) => {
      queryClient.setQueryData(["incident", workspace.id, incidentId], updated);
      await queryClient.invalidateQueries({ queryKey: ["incidents", workspace.id] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard", workspace.id] });
    },
    onError: (err) => setActionError(err instanceof ApiError ? err.message : "Failed to update incident."),
  });

  if (incidentQuery.isLoading) return <PageSpinner />;

  if (incidentQuery.error || !incident) {
    return (
      <Alert tone="error">
        {incidentQuery.error instanceof ApiError ? incidentQuery.error.message : "Failed to load incident."}
      </Alert>
    );
  }

  const canManage = workspace.role === "owner" || workspace.role === "admin";

  return (
    <div className="space-y-6">
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold text-slate-900">{incident.title}</h1>
          <IncidentStatusBadge status={incident.status} />
          <IncidentSeverityBadge severity={incident.severity} />
        </div>
        <p className="mt-1 text-sm text-slate-500">
          Monitor:{" "}
          <Link href={`/workspaces/${workspace.id}/monitors/${incident.monitor_id}`} className="hover:underline">
            {monitorQuery.data?.name ?? incident.monitor_id}
          </Link>
        </p>
      </div>

      {actionError && <Alert tone="error">{actionError}</Alert>}

      <Card>
        <CardHeader>
          <CardTitle>Timeline</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-slate-600">
          <p>Opened: {formatDateTime(incident.created_at)}</p>
          <p>Last updated: {formatDateTime(incident.updated_at)}</p>
          <p>Resolved: {formatDateTime(incident.resolved_at)}</p>
        </CardContent>
      </Card>

      {canManage && incident.status !== "resolved" && (
        <div className="flex gap-2">
          {incident.status === "open" && (
            <Button
              variant="secondary"
              isLoading={updateMutation.isPending}
              onClick={() => {
                setActionError(null);
                updateMutation.mutate("investigating");
              }}
            >
              Acknowledge (mark investigating)
            </Button>
          )}
          <Button
            variant="primary"
            isLoading={updateMutation.isPending}
            onClick={() => {
              setActionError(null);
              updateMutation.mutate("resolved");
            }}
          >
            Resolve
          </Button>
        </div>
      )}
    </div>
  );
}
