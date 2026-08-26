import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { issueDevToken } from "../api/client";
import type { UserRole } from "../api/types";

interface AuthState {
  userId: string;
  role: UserRole;
  token: string;
}

interface AuthContextValue {
  auth: AuthState | null;
  login: (userId: string, role: UserRole) => Promise<void>;
  logout: () => void;
}

const STORAGE_KEY = "fca_demo_auth";

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function loadStoredAuth(): AuthState | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuthState) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState | null>(() => loadStoredAuth());

  const login = useCallback(async (userId: string, role: UserRole) => {
    const { access_token } = await issueDevToken(userId, role);
    const next: AuthState = { userId, role, token: access_token };
    setAuth(next);
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }, []);

  const logout = useCallback(() => {
    setAuth(null);
    window.sessionStorage.removeItem(STORAGE_KEY);
  }, []);

  const value = useMemo(() => ({ auth, login, logout }), [auth, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
