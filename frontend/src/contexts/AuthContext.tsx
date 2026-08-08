import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { tokenStore } from "../api/tokenStore";
import * as authService from "../services/authService";
import type { AuthUser } from "../types/auth";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  user: AuthUser | null;
  status: AuthStatus;
  signIn: (identifier: string, password: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    let active = true;

    async function restoreSession() {
      if (!tokenStore.getRefresh()) {
        if (active) setStatus("anonymous");
        return;
      }
      try {
        const restoredUser = await authService.getCurrentUser();
        if (active) {
          setUser(restoredUser);
          setStatus("authenticated");
        }
      } catch {
        authService.logout();
        if (active) {
          setUser(null);
          setStatus("anonymous");
        }
      }
    }

    void restoreSession();
    return () => {
      active = false;
    };
  }, []);

  async function signIn(identifier: string, password: string) {
    const authenticatedUser = await authService.login(identifier, password);
    setUser(authenticatedUser);
    setStatus("authenticated");
  }

  function signOut() {
    authService.logout();
    setUser(null);
    setStatus("anonymous");
  }

  const value = useMemo(
    () => ({ user, status, signIn, signOut }),
    [user, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth debe utilizarse dentro de AuthProvider.");
  return context;
}

