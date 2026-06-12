"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { FieldError, Input, Label, Select } from "@/components/ui/Input";
import { ApiError, monitorApi } from "@/lib/api";
import type { MonitorType } from "@/lib/types";
import { useWorkspace } from "@/lib/workspace-context";

const schema = z.object({
  name: z.string().min(1, "Name is required.").max(255),
  monitor_type: z.enum(["http", "tcp", "ping"]),
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

type FormValues = z.infer<typeof schema>;

const targetPlaceholders: Record<MonitorType, string> = {
  http: "https://example.com/health",
  tcp: "example.com:443",
  ping: "example.com",
};

const targetHints: Record<MonitorType, string> = {
  http: "Absolute http:// or https:// URL.",
  tcp: "host:port, with a port between 1 and 65535.",
  ping: "A bare hostname or IP address (no scheme, path, or port).",
};

export default function NewMonitorPage() {
  const workspace = useWorkspace();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      monitor_type: "http",
      target: "",
      check_interval_seconds: 60,
      failure_threshold: 3,
      is_active: true,
    },
  });

  const monitorType = watch("monitor_type");

  const createMutation = useMutation({
    mutationFn: (values: FormValues) => monitorApi.create(workspace.id, values),
    onSuccess: async (monitor) => {
      await queryClient.invalidateQueries({ queryKey: ["monitors", workspace.id] });
      router.push(`/workspaces/${workspace.id}/monitors/${monitor.id}`);
    },
    onError: (err) => setFormError(err instanceof ApiError ? err.message : "Failed to create monitor."),
  });

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="text-xl font-semibold text-slate-900">New monitor</h1>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Monitor details</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={handleSubmit((values) => {
              setFormError(null);
              createMutation.mutate(values);
            })}
          >
            {formError && <Alert tone="error">{formError}</Alert>}

            <div>
              <Label htmlFor="name">Name</Label>
              <Input id="name" placeholder="API health check" {...register("name")} />
              <FieldError>{errors.name?.message}</FieldError>
            </div>

            <div>
              <Label htmlFor="monitor_type">Type</Label>
              <Select id="monitor_type" {...register("monitor_type")}>
                <option value="http">HTTP</option>
                <option value="tcp">TCP</option>
                <option value="ping">Ping</option>
              </Select>
            </div>

            <div>
              <Label htmlFor="target">Target</Label>
              <Input id="target" placeholder={targetPlaceholders[monitorType]} {...register("target")} />
              <p className="mt-1 text-xs text-slate-500">{targetHints[monitorType]}</p>
              <FieldError>{errors.target?.message}</FieldError>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="check_interval_seconds">Check interval (seconds)</Label>
                <Input
                  id="check_interval_seconds"
                  type="number"
                  min={30}
                  max={86400}
                  {...register("check_interval_seconds", { valueAsNumber: true })}
                />
                <FieldError>{errors.check_interval_seconds?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="failure_threshold">Failure threshold</Label>
                <Input
                  id="failure_threshold"
                  type="number"
                  min={1}
                  max={100}
                  {...register("failure_threshold", { valueAsNumber: true })}
                />
                <FieldError>{errors.failure_threshold?.message}</FieldError>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                id="is_active"
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                {...register("is_active")}
              />
              <Label htmlFor="is_active" className="mb-0">
                Active (start checking immediately)
              </Label>
            </div>

            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => router.back()}>
                Cancel
              </Button>
              <Button type="submit" isLoading={isSubmitting || createMutation.isPending}>
                Create monitor
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
