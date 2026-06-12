"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { PageSpinner } from "@/components/ui/Spinner";
import { useAuth } from "@/lib/auth-context";

export default function Home() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    router.replace(user ? "/workspaces" : "/login");
  }, [user, isLoading, router]);

  return <PageSpinner />;
}
