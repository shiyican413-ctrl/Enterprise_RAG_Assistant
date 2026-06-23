"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { clearAccessToken, getCurrentUser, type CurrentUser } from "@/lib/auth";

type AuthState = {
  user: CurrentUser | null;
  loading: boolean;
  refresh: () => Promise<CurrentUser | null>;
  setUser: (user: CurrentUser | null) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    const next = await getCurrentUser().catch(() => null);
    setUser(next);
    setLoading(false);
    return next;
  }

  useEffect(() => { void refresh(); }, []);

  return (
    <AuthContext.Provider value={{
      user, loading, refresh, setUser,
      logout: () => { clearAccessToken(); setUser(null); },
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
