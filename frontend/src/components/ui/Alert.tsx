import { type HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type Tone = "error" | "success" | "info";

interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  tone?: Tone;
}

const toneClasses: Record<Tone, string> = {
  error: "bg-red-50 text-red-700 border-red-200",
  success: "bg-green-50 text-green-700 border-green-200",
  info: "bg-blue-50 text-blue-700 border-blue-200",
};

export function Alert({ className, tone = "info", ...props }: AlertProps) {
  return (
    <div className={cn("rounded-md border px-3 py-2 text-sm", toneClasses[tone], className)} {...props} />
  );
}
