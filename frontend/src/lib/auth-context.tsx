"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { authApi, clearTokens, getAccessToken, setTokens } from "./api";
import type { User } from "./types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; password: string; full_name?: string }) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadUser = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      const me = await authApi.me();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Bootstrapping session state from localStorage on mount is exactly the
    // "external system sync" case useEffect exists for; React Compiler's
    // set-state-in-effect rule doesn't have an exception for it yet.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadUser();

    const handleUnauthorized = () => setUser(null);
    window.addEventListener("sentinel:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("sentinel:unauthorized", handleUnauthorized);
  }, [loadUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const token = await authApi.login(email, password);
      setTokens(token);
      await loadUser();
    },
    [loadUser],
  );

  const register = useCallback(
    async (data: { email: string; password: string; full_name?: string }) => {
      await authApi.register(data);
      await login(data.email, data.password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      clearTokens();
      setUser(null);
    }
  }, []);

  return <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
