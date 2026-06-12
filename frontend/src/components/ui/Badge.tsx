import { type HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type Tone = "neutral" | "green" | "red" | "amber" | "blue" | "purple";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

const toneClasses: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700",
  green: "bg-green-100 text-green-800",
  red: "bg-red-100 text-red-800",
  amber: "bg-amber-100 text-amber-800",
  blue: "bg-blue-100 text-blue-800",
  purple: "bg-purple-100 text-purple-800",
};

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
        toneClasses[tone],
        className,
      )}
      {...props}
    />
  );
}

const monitorStatusTone: Record<string, Tone> = {
  up: "green",
  down: "red",
  pending: "amber",
};

const incidentStatusTone: Record<string, Tone> = {
  open: "red",
  investigating: "amber",
  resolved: "green",
};

const incidentSeverityTone: Record<string, Tone> = {
  minor: "blue",
  major: "amber",
  critical: "red",
};

const workspaceRoleTone: Record<string, Tone> = {
  owner: "purple",
  admin: "blue",
  member: "neutral",
};

export function MonitorStatusBadge({ status }: { status: string }) {
  return <Badge tone={monitorStatusTone[status] ?? "neutral"}>{status}</Badge>;
}

export function IncidentStatusBadge({ status }: { status: string }) {
  return <Badge tone={incidentStatusTone[status] ?? "neutral"}>{status}</Badge>;
}

export function IncidentSeverityBadge({ severity }: { severity: string }) {
  return <Badge tone={incidentSeverityTone[severity] ?? "neutral"}>{severity}</Badge>;
}

export function WorkspaceRoleBadge({ role }: { role: string }) {
  return <Badge tone={workspaceRoleTone[role] ?? "neutral"}>{role}</Badge>;
}
