import { resolveBaseUrl } from "./api";
import type {
  AdminUserUpdateRequest,
  AuditEntry,
  AuthMode,
  AuthUser,
  OAuthStartResponse,
  TokenPair,
} from "../types/auth";

type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE";

interface RequestOptions<T> {
  method?: HttpMethod;
  body?: T;
  headers?: Record<string, string>;
  cache?: RequestCache;
}

async function authRequest<TBody = unknown, TResult = unknown>(
  path: string,
  options: RequestOptions<TBody> = {},
): Promise<TResult> {
  const baseUrl = resolveBaseUrl();
  const url = new URL(path, baseUrl);
  const { method = "GET", body, headers = {}, cache = "no-store" } = options;

  const response = await fetch(url.toString(), {
    method,
    cache,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (response.status === 204) {
    return undefined as TResult;
  }

  if (response.status === 202) {
    let message = "Request accepted";
    try {
      const payload = await response.json();
      if (payload && typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch (error) {
      message = "Request accepted";
    }
    throw new Error(message);
  }

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return (await response.json()) as TResult;
}

export async function setupBootstrap(payload: {
  email: string;
  password: string;
  username?: string;
}): Promise<TokenPair> {
  return authRequest<typeof payload, TokenPair>("/api/setup", {
    method: "POST",
    body: payload,
  });
}

export async function login(payload: {
  email: string;
  password: string;
  remember_me?: boolean;
}): Promise<TokenPair> {
  return authRequest<typeof payload, TokenPair>("/api/auth/login", {
    method: "POST",
    body: payload,
  });
}

export async function register(payload: {
  email: string;
  password: string;
  username?: string;
}): Promise<TokenPair> {
  return authRequest<typeof payload, TokenPair>("/api/auth/register", {
    method: "POST",
    body: payload,
  });
}

export async function logout(): Promise<void> {
  await authRequest("/api/auth/logout", { method: "POST" });
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  return authRequest<undefined, AuthUser>("/api/auth/me");
}

export async function forgotPassword(payload: { email: string }): Promise<void> {
  await authRequest<typeof payload, void>("/api/auth/password/forgot", {
    method: "POST",
    body: payload,
  });
}

export async function resetPassword(payload: { token: string; password: string }): Promise<void> {
  await authRequest<typeof payload, void>("/api/auth/password/reset", {
    method: "POST",
    body: payload,
  });
}

export async function startOAuth(redirectTo?: string): Promise<OAuthStartResponse> {
  const query = redirectTo ? `?redirect_to=${encodeURIComponent(redirectTo)}` : "";
  return authRequest<undefined, OAuthStartResponse>(`/api/auth/oauth/start${query}`);
}

export async function completeOAuth(payload: {
  code: string;
  state: string;
  redirect_uri: string;
}): Promise<TokenPair> {
  return authRequest<typeof payload, TokenPair>("/api/auth/oauth/callback", {
    method: "POST",
    body: payload,
  });
}

export async function refreshToken(): Promise<TokenPair> {
  return authRequest<undefined, TokenPair>("/api/auth/token/refresh", {
    method: "POST",
  });
}

export async function getAuthMode(): Promise<{ auth_mode: AuthMode }> {
  return authRequest<undefined, { auth_mode: AuthMode }>("/api/auth/mode");
}

export async function fetchAdminUsers(): Promise<{ users: AuthUser[] }> {
  return authRequest<undefined, { users: AuthUser[] }>("/api/admin/users");
}

export async function updateAdminUser(id: string, payload: AdminUserUpdateRequest): Promise<AuthUser> {
  return authRequest<typeof payload, AuthUser>(`/api/admin/users/${id}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function syncAdminUsers(payload: { emails: string[]; source?: string }): Promise<{ created: number }> {
  return authRequest<typeof payload, { created: number }>("/api/admin/users/sync", {
    method: "POST",
    body: payload,
  });
}

export async function fetchAuditLog(): Promise<{ entries: AuditEntry[] }> {
  return authRequest<undefined, { entries: AuditEntry[] }>("/api/admin/audit");
}
