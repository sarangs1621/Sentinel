"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="auth-page">
      <div className="auth-card" style={{ textAlign: "center" }}>
        <div className="auth-logo">
          <div className="auth-logo-icon">S</div>
          <span className="auth-logo-text">Sentinel</span>
        </div>
        <div style={{ fontSize: "2.5rem", marginBottom: 8 }}>⚠️</div>
        <h1 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: 8 }}>Something went wrong</h1>
        <p className="text-sm text-muted" style={{ marginBottom: 24 }}>
          An unexpected error occurred. You can try again or return to the homepage.
        </p>
        <div className="flex gap-3" style={{ justifyContent: "center" }}>
          <button className="btn btn-secondary" onClick={reset}>Try again</button>
          <Link href="/" className="btn btn-primary">Go home</Link>
        </div>
      </div>
    </div>
  );
}
