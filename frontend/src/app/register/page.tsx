"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiRegister, apiLogin, ApiError, setTokens } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await apiRegister(email, password, fullName || undefined);
      const tokens = await apiLogin(email, password);
      setTokens(tokens.access_token, tokens.refresh_token);
      router.push("/workspaces");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("An unexpected error occurred. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="auth-logo-icon">S</div>
          <span className="auth-logo-text">Sentinel</span>
        </div>
        <h1 className="auth-title">Create your account</h1>
        <p className="auth-subtitle">Start monitoring in under a minute</p>

        {error && <div className="auth-error">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="input-label" htmlFor="register-name">
              Full name
            </label>
            <input
              id="register-name"
              type="text"
              className="input-field"
              placeholder="Jane Doe"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              autoComplete="name"
              autoFocus
            />
          </div>
          <div className="form-group">
            <label className="input-label" htmlFor="register-email">
              Email address
            </label>
            <input
              id="register-email"
              type="email"
              className="input-field"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div className="form-group">
            <label className="input-label" htmlFor="register-password">
              Password
            </label>
            <input
              id="register-password"
              type="password"
              className="input-field"
              placeholder="Min 8 chars, with a letter and digit"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
              minLength={8}
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
                Creating account…
              </>
            ) : (
              "Create account"
            )}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account?{" "}
          <Link href="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
