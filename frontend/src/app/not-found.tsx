import Link from "next/link";

export default function NotFound() {
  return (
    <div className="auth-page">
      <div className="auth-card" style={{ textAlign: "center" }}>
        <div className="auth-logo">
          <div className="auth-logo-icon">S</div>
          <span className="auth-logo-text">Sentinel</span>
        </div>
        <div
          style={{
            fontSize: "3rem",
            fontWeight: 800,
            marginBottom: 8,
            background: "var(--accent-gradient)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
          }}
        >
          404
        </div>
        <h1 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: 8 }}>Page not found</h1>
        <p className="text-sm text-muted" style={{ marginBottom: 24 }}>
          The page you&apos;re looking for doesn&apos;t exist or may have been moved.
        </p>
        <Link href="/" className="btn btn-primary" style={{ width: "100%" }}>
          Go home
        </Link>
      </div>
    </div>
  );
}
