import type { ApiFailure, ApiSuccess, AuthTokens } from "../types/auth";
import { tokenStore } from "./tokenStore";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";
const API_BASE_URL = configuredBaseUrl.replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  errors: Record<string, unknown>;

  constructor(message: string, status = 0, errors: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errors = errors;
  }
}

let refreshPromise: Promise<string> | null = null;

function endpointUrl(path: string): string {
  return `${API_BASE_URL}/${path.replace(/^\//, "")}`;
}

async function parseResponse<T>(response: Response): Promise<ApiSuccess<T>> {
  const payload = (await response.json().catch(() => null)) as ApiSuccess<T> | ApiFailure | null;
  if (!response.ok || !payload || !payload.success) {
    const failure = payload as ApiFailure | null;
    throw new ApiError(
      failure?.message ?? "No fue posible comunicarse con Memora.",
      response.status,
      failure?.errors ?? {},
    );
  }
  return payload;
}

export async function refreshAccessToken(): Promise<string> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const refresh = tokenStore.getRefresh();
    if (!refresh) throw new ApiError("La sesión ha finalizado.", 401);

    const response = await fetch(endpointUrl("auth/refresh/"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ refresh }),
    });

    const payload = await parseResponse<Partial<AuthTokens> & { access: string }>(response);
    tokenStore.setAccess(payload.data.access);
    if (payload.data.refresh) tokenStore.setRefresh(payload.data.refresh);
    return payload.data.access;
  })()
    .catch((error: unknown) => {
      tokenStore.clear();
      throw error;
    })
    .finally(() => {
      refreshPromise = null;
    });

  return refreshPromise;
}

interface RequestOptions extends RequestInit {
  authenticated?: boolean;
  retryOnUnauthorized?: boolean;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    authenticated = true,
    retryOnUnauthorized = true,
    headers: providedHeaders,
    ...requestOptions
  } = options;
  const headers = new Headers(providedHeaders);
  headers.set("Accept", "application/json");
  if (requestOptions.body && !(requestOptions.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (authenticated) {
    let access = tokenStore.getAccess();
    if (!access && tokenStore.getRefresh()) access = await refreshAccessToken();
    if (access) headers.set("Authorization", `Bearer ${access}`);
  }

  const response = await fetch(endpointUrl(path), { ...requestOptions, headers });
  if (response.status === 401 && authenticated && retryOnUnauthorized && tokenStore.getRefresh()) {
    await refreshAccessToken();
    return apiRequest<T>(path, { ...options, retryOnUnauthorized: false });
  }

  const payload = await parseResponse<T>(response);
  return payload.data;
}

