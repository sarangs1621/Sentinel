"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { z } from "zod";

import { Alert } from "@/components/ui/Alert";
import { Badge, MonitorStatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { FieldError, Input, Label } from "@/components/ui/Input";
import { PageSpinner } from "@/components/ui/Spinner";
import { ApiError, monitorApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { canManageMonitor, formatDateTime, formatMs, formatPercent, formatRelativeTime } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace-context";

const editSchema = z.object({
  name: z.string().min(1, "Name is required.").max(255),
  target: z.string().min(1, "Target is required.").max(512),
  check_interval_seconds: z
    .number({ message: "Enter a number." })
    .int("Must be a whole number.")
    .min(30, "Minimum interval is 30 seconds.")
    .max(86400, "Maximum interval is 86400 seconds (24 hours)."),
  failure_threshold: z
    .number({ message: "Enter a number." })
    .int("Must be a whole number.")
    .min(1, "Minimum is 1.")
    .max(100, "Maximum is 100."),
  is_active: z.boolean(),
});
type EditFormValues = z.infer<typeof editSchema>;

export default function MonitorDetailPage() {
  const workspace = useWorkspace();
  const { user } = useAuth();
  const params = useParams<{ monitorId: string }>();
  const monitorId = params.monitorId;
  const router = useRouter();
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const monitorQuery = useQuery({
    queryKey: ["monitor", workspace.id, monitorId],
    queryFn: () => monitorApi.get(workspace.id, monitorId),
  });

  const checksQuery = useQuery({
    queryKey: ["monitor-checks", workspace.id, monitorId],
    queryFn: () => monitorApi.checks(workspace.id, monitorId),
  });

  const latencyQuery = useQuery({
    queryKey: ["monitor-latency", workspace.id, monitorId],
    queryFn: () => monitorApi.latency(workspace.id, monitorId),
  });

  const uptimeQuery = useQuery({
    queryKey: ["monitor-uptime", workspace.id, monitorId],
    queryFn: () => monitorApi.uptime(workspace.id, monitorId),
  });

  const monitor = monitorQuery.data;

  const editForm = useForm<EditFormValues>({ resolver: zodResolver(editSchema) });

  useEffect(() => {
    if (monitor) {
      editForm.reset({
        name: monitor.name,
        target: monitor.target,
        check_interval_seconds: monitor.check_interval_seconds,
        failure_threshold: monitor.failure_threshold,
        is_active: monitor.is_active,
      });
    }
  }, [monitor, editForm]);

  const updateMutation = useMutation({
    mutationFn: (values: EditFormValues) => monitorApi.update(workspace.id, monitorId, values),
    onSuccess: async (updated) => {
      queryClient.setQueryData(["monitor", workspace.id, monitorId], updated);
      await queryClient.invalidateQueries({ queryKey: ["monitors", workspace.id] });
      setIsEditing(false);
    },
    onError: (err) => setActionError(err instanceof ApiError ? err.message : "Failed to update monitor."),
  });

  const deleteMutation = useMutation({
    mutationFn: () => monitorApi.remove(workspace.id, monitorId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["monitors", workspace.id] });
      router.push(`/workspaces/${workspace.id}/monitors`);
    },
    onError: (err) => setActionError(err instanceof ApiError ? err.message : "Failed to delete monitor."),
  });

  if (monitorQuery.isLoading) return <PageSpinner />;

  if (monitorQuery.error || !monitor) {
    return (
      <Alert tone="error">
        {monitorQuery.error instanceof ApiError ? monitorQuery.error.message : "Failed to load monitor."}
      </Alert>
    );
  }

  const canManage = canManageMonitor(workspace, monitor, user?.id);
  const checks = checksQuery.data ?? [];
  const recentChecks = checks.slice(0, 25);
  const chartData = [...recentChecks].reverse().map((check) => ({
    time: new Date(check.created_at).toLocaleTimeString(),
    ms: check.response_time_ms,
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-slate-900">{monitor.name}</h1>
            <MonitorStatusBadge status={monitor.status} />
            {!monitor.is_active && <Badge tone="neutral">Paused</Badge>}
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {monitor.monitor_type.toUpperCase()} &middot; {monitor.target}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            Checks every {monitor.check_interval_seconds}s &middot; {monitor.consecutive_failures}/
            {monitor.failure_threshold} consecutive failures &middot; last checked{" "}
            {formatRelativeTime(monitor.last_checked_at)}
          </p>
        </div>
        {canManage && (
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setIsEditing((v) => !v)}>
              {isEditing ? "Cancel" : "Edit"}
            </Button>
            <Button
              variant="danger"
              size="sm"
              isLoading={deleteMutation.isPending}
              onClick={() => {
                if (window.confirm(`Delete monitor "${monitor.name}"? This cannot be undone.`)) {
                  setActionError(null);
                  deleteMutation.mutate();
                }
              }}
            >
              Delete
            </Button>
          </div>
        )}
      </div>

      {actionError && <Alert tone="error">{actionError}</Alert>}

      {isEditing && (
        <Card>
          <CardHeader>
            <CardTitle>Edit monitor</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-4"
              onSubmit={editForm.handleSubmit((values) => {
                setActionError(null);
                updateMutation.mutate(values);
              })}
            >
              <div>
                <Label htmlFor="edit-name">Name</Label>
                <Input id="edit-name" {...editForm.register("name")} />
                <FieldError>{editForm.formState.errors.name?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="edit-target">Target</Label>
                <Input id="edit-target" {...editForm.register("target")} />
                <FieldError>{editForm.formState.errors.target?.message}</FieldError>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="edit-interval">Check interval (seconds)</Label>
                  <Input
                    id="edit-interval"
                    type="number"
                    min={30}
                    max={86400}
                    {...editForm.register("check_interval_seconds", { valueAsNumber: true })}
                  />
                  <FieldError>{editForm.formState.errors.check_interval_seconds?.message}</FieldError>
                </div>
                <div>
                  <Label htmlFor="edit-threshold">Failure threshold</Label>
                  <Input
                    id="edit-threshold"
                    type="number"
                    min={1}
                    max={100}
                    {...editForm.register("failure_threshold", { valueAsNumber: true })}
                  />
                  <FieldError>{editForm.formState.errors.failure_threshold?.message}</FieldError>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  id="edit-is-active"
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  {...editForm.register("is_active")}
                />
                <Label htmlFor="edit-is-active" className="mb-0">
                  Active
                </Label>
              </div>
              <div className="flex justify-end">
                <Button type="submit" isLoading={updateMutation.isPending}>
                  Save changes
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Uptime (24h)" value={formatPercent(uptimeQuery.data?.uptime_percentage)} />
        <StatCard label="Check pass rate (24h)" value={formatPercent(uptimeQuery.data?.check_pass_ratio)} />
        <StatCard label="Avg latency (24h)" value={formatMs(latencyQuery.data?.avg_response_time_ms)} />
        <StatCard label="p95 latency (24h)" value={formatMs(latencyQuery.data?.p95_response_time_ms)} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Response time (recent checks)</CardTitle>
        </CardHeader>
        <CardContent>
          {chartData.length === 0 ? (
            <p className="text-sm text-slate-500">No checks recorded yet.</p>
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <XAxis dataKey="time" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} unit="ms" />
                  <Tooltip />
                  <Line type="monotone" dataKey="ms" stroke="#2563eb" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent checks</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {recentChecks.length === 0 ? (
            <p className="px-4 py-4 text-sm text-slate-500">No checks recorded yet.</p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Response time</th>
                  <th className="px-4 py-2">Error</th>
                  <th className="px-4 py-2">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recentChecks.map((check) => (
                  <tr key={check.id}>
                    <td className="px-4 py-2">
                      <Badge tone={check.status === "success" ? "green" : "red"}>{check.status}</Badge>
                    </td>
                    <td className="px-4 py-2 text-slate-500">{formatMs(check.response_time_ms)}</td>
                    <td className="max-w-xs truncate px-4 py-2 text-slate-500">{check.error_message ?? "—"}</td>
                    <td className="px-4 py-2 text-slate-500">{formatDateTime(check.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
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
