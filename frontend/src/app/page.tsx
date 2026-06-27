"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      router.replace("/workspaces");
    } else {
      router.replace("/login");
    }
  }, [router]);

  return (
    <div className="loading-page">
      <div className="spinner spinner-lg" />
    </div>
  );
}
