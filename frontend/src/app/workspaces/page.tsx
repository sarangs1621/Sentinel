"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AuthGuard } from "@/components/AuthGuard";
import { Alert } from "@/components/ui/Alert";
import { WorkspaceRoleBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { FieldError, Input, Label } from "@/components/ui/Input";
import { PageSpinner } from "@/components/ui/Spinner";
import { ApiError, workspaceApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const createSchema = z.object({
  name: z.string().min(1, "Name is required.").max(255),
  description: z.string().max(2000).optional().or(z.literal("")),
});
type CreateFormValues = z.infer<typeof createSchema>;

const joinSchema = z.object({
  invite_code: z.string().min(1, "Invite code is required.").max(64),
});
type JoinFormValues = z.infer<typeof joinSchema>;

export default function WorkspacesPage() {
  return (
    <AuthGuard>
      <WorkspacesContent />
    </AuthGuard>
  );
}

function WorkspacesContent() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [createError, setCreateError] = useState<string | null>(null);
  const [joinError, setJoinError] = useState<string | null>(null);

  const {
    data: workspaces,
    isLoading,
    error,
  } = useQuery({ queryKey: ["workspaces"], queryFn: workspaceApi.list });

  const createForm = useForm<CreateFormValues>({ resolver: zodResolver(createSchema) });
  const joinForm = useForm<JoinFormValues>({ resolver: zodResolver(joinSchema) });

  const createMutation = useMutation({
    mutationFn: (values: CreateFormValues) =>
      workspaceApi.create({ name: values.name, description: values.description || undefined }),
    onSuccess: async (workspace) => {
      await queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      router.push(`/workspaces/${workspace.id}/dashboard`);
    },
    onError: (err) => setCreateError(err instanceof ApiError ? err.message : "Failed to create workspace."),
  });

  const joinMutation = useMutation({
    mutationFn: (values: JoinFormValues) => workspaceApi.join(values.invite_code),
    onSuccess: async (workspace) => {
      await queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      router.push(`/workspaces/${workspace.id}/dashboard`);
    },
    onError: (err) => setJoinError(err instanceof ApiError ? err.message : "Failed to join workspace."),
  });

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
        <span className="text-lg font-semibold text-slate-900">Sentinel</span>
        <div className="flex items-center gap-3">
          <span className="hidden text-sm text-slate-500 sm:inline">{user?.email}</span>
          <Button variant="ghost" size="sm" onClick={() => void logout()}>
            Log out
          </Button>
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-8 sm:px-6">
        <h1 className="text-xl font-semibold text-slate-900">Your workspaces</h1>
        <p className="mt-1 text-sm text-slate-500">Pick a workspace to view its monitors, incidents, and dashboard.</p>

        <div className="mt-6 space-y-3">
          {isLoading && <PageSpinner />}
          {error && <Alert tone="error">{error instanceof ApiError ? error.message : "Failed to load workspaces."}</Alert>}
          {workspaces?.length === 0 && (
            <Alert tone="info">You aren&apos;t a member of any workspace yet. Create one or join with an invite code below.</Alert>
          )}
          {workspaces?.map((workspace) => (
            <Link key={workspace.id} href={`/workspaces/${workspace.id}/dashboard`}>
              <Card className="transition-shadow hover:shadow-md">
                <CardContent className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-slate-900">{workspace.name}</p>
                    {workspace.description && <p className="text-sm text-slate-500">{workspace.description}</p>}
                  </div>
                  <WorkspaceRoleBadge role={workspace.role} />
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>

        <div className="mt-8 grid gap-6 sm:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Create a workspace</CardTitle>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-3"
                onSubmit={createForm.handleSubmit((values) => {
                  setCreateError(null);
                  createMutation.mutate(values);
                })}
              >
                {createError && <Alert tone="error">{createError}</Alert>}
                <div>
                  <Label htmlFor="create-name">Name</Label>
                  <Input id="create-name" {...createForm.register("name")} />
                  <FieldError>{createForm.formState.errors.name?.message}</FieldError>
                </div>
                <div>
                  <Label htmlFor="create-description">Description (optional)</Label>
                  <Input id="create-description" {...createForm.register("description")} />
                  <FieldError>{createForm.formState.errors.description?.message}</FieldError>
                </div>
                <Button type="submit" isLoading={createMutation.isPending} className="w-full">
                  Create workspace
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Join a workspace</CardTitle>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-3"
                onSubmit={joinForm.handleSubmit((values) => {
                  setJoinError(null);
                  joinMutation.mutate(values);
                })}
              >
                {joinError && <Alert tone="error">{joinError}</Alert>}
                <div>
                  <Label htmlFor="invite-code">Invite code</Label>
                  <Input id="invite-code" {...joinForm.register("invite_code")} />
                  <FieldError>{joinForm.formState.errors.invite_code?.message}</FieldError>
                </div>
                <Button type="submit" variant="secondary" isLoading={joinMutation.isPending} className="w-full">
                  Join workspace
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
