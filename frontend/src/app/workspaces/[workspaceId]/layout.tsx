"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { type ReactNode } from "react";

import { AuthGuard } from "@/components/AuthGuard";
import { WorkspaceShell } from "@/components/layout/WorkspaceShell";
import { Alert } from "@/components/ui/Alert";
import { PageSpinner } from "@/components/ui/Spinner";
import { ApiError, workspaceApi } from "@/lib/api";
import { WorkspaceProvider } from "@/lib/workspace-context";

export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  const params = useParams<{ workspaceId: string }>();

  return (
    <AuthGuard>
      <WorkspaceLayoutContent workspaceId={params.workspaceId}>{children}</WorkspaceLayoutContent>
    </AuthGuard>
  );
}

function WorkspaceLayoutContent({ workspaceId, children }: { workspaceId: string; children: ReactNode }) {
  const {
    data: workspace,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["workspace", workspaceId],
    queryFn: () => workspaceApi.get(workspaceId),
  });

  if (isLoading) {
    return <PageSpinner />;
  }

  if (error || !workspace) {
    return (
      <div className="p-6">
        <Alert tone="error">{error instanceof ApiError ? error.message : "Failed to load workspace."}</Alert>
      </div>
    );
  }

  return (
    <WorkspaceProvider workspace={workspace}>
      <WorkspaceShell workspace={workspace}>{children}</WorkspaceShell>
    </WorkspaceProvider>
  );
}
