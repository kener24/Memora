import { apiRequest } from "../api/client";
import { tokenStore } from "../api/tokenStore";
import type { AuthTokens, AuthUser } from "../types/auth";

export async function login(identifier: string, password: string): Promise<AuthUser> {
  const tokens = await apiRequest<AuthTokens>("auth/login/", {
    method: "POST",
    authenticated: false,
    body: JSON.stringify({ identifier, password }),
  });
  tokenStore.setAccess(tokens.access);
  tokenStore.setRefresh(tokens.refresh);

  try {
    return await getCurrentUser();
  } catch (error) {
    tokenStore.clear();
    throw error;
  }
}

export function getCurrentUser(): Promise<AuthUser> {
  return apiRequest<AuthUser>("auth/me/");
}

export function logout(): void {
  tokenStore.clear();
}

