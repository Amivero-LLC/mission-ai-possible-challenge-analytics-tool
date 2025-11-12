import type { DatabaseStatus, ReloadMode, ReloadResource, ReloadRun } from "../types/admin";
import type { CampaignSummaryResponse, SubmissionReloadSummary } from "../types/campaign";
import type { DashboardResponse, SortOption } from "../types/dashboard";
import { buildBrowserAuthHeaders } from "./browserAuth";

/**
 * Supported query parameters for `/dashboard`.
 *
 * Properties mirror the FastAPI endpoint signature. Optional fields are omitted
 * when undefined so the backend can fall back to its default filters.
 */
export interface DashboardQuery {
  sort_by?: SortOption;
  week?: string;
  challenge?: string;
  user_id?: string;
  status?: string;
}

/**
 * Resolve the API base URL for either server-side or client-side environments.
 *
 * Priority order:
 *   1. `API_BASE_URL` (server only—allows calling Docker service names)
 *   2. `NEXT_PUBLIC_API_BASE_URL`
 *   3. `http://localhost:8000` fallback for local development
 *
 * Returns:
 *   string – absolute URL used to build dashboard requests.
 */
export function resolveBaseUrl() {
  if (typeof window === "undefined") {
    return (
      process.env.API_BASE_URL ??
      process.env.NEXT_PUBLIC_API_BASE_URL ??
      "http://localhost:8000"
    );
  }
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

function composeAuthHeaders(authCookies?: string): Record<string, string> {
  const headers: Record<string, string> = {
    ...buildBrowserAuthHeaders(),
  };
  if (authCookies) {
    headers.Cookie = authCookies;
  }
  return headers;
}

/**
 * Fetch the mission dashboard payload from the FastAPI backend.
 *
 * Args:
 *   query (DashboardQuery): Optional filter/sort parameters. Numbers are
 *     converted to strings for the query string.
 *
 * Returns:
 *   Promise<DashboardResponse> – hydrated mission analytics payload.
 *
 * Errors:
 *   - Throws a generic Error with the backend response body when the HTTP
 *     status is not OK. Callers should capture and surface the message.
 *
 * Side Effects:
 *   - Issues an HTTP GET to `/dashboard`; cache disabled to ensure fresh data.
 *
 * Example:
 *   const dashboard = await fetchDashboard({ week: 2, sort_by: "attempts" });
 */
export async function fetchDashboard(
  query: DashboardQuery = {},
  authCookies?: string,
): Promise<DashboardResponse> {
  const baseUrl = resolveBaseUrl();
  const url = new URL("/dashboard", baseUrl);
  const params = new URLSearchParams();

  if (query.sort_by) params.set("sort_by", query.sort_by);
  if (query.week) params.set("week", query.week);
  if (query.challenge) params.set("challenge", query.challenge);
  if (query.user_id) params.set("user_id", query.user_id);
  if (query.status) params.set("status", query.status);

  if (params.size > 0) {
    url.search = params.toString();
  }

  // Disable HTTP caching so the UI always reflects the most recent OpenWebUI snapshot.
  const headers = composeAuthHeaders(authCookies);

  const response = await fetch(url.toString(), {
    cache: "no-store",
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<DashboardResponse>;
}

/**
 * Trigger a manual refresh of data from Open WebUI API.
 *
 * Returns:
 *   Promise<{status: string, message: string, last_fetched: string, data_source: string}>
 *
 * Errors:
 *   - Throws an Error if the refresh fails or API credentials are not configured
 *
 * Side Effects:
 *   - Issues an HTTP POST to `/refresh`
 *   - Forces a fresh fetch from Open WebUI and saves to cache
 *
 * Example:
 *   const result = await refreshData();
 */
export async function refreshData(authCookies?: string): Promise<{
  status: string;
  message: string;
  last_fetched: string;
  data_source: string;
}> {
  const baseUrl = resolveBaseUrl();
  const url = new URL("/refresh", baseUrl);

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...composeAuthHeaders(authCookies),
  };

  const response = await fetch(url.toString(), {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return response.json();
}

export async function fetchDatabaseStatus(authCookies?: string): Promise<DatabaseStatus> {
  const baseUrl = resolveBaseUrl();
  const url = new URL("/admin/db/status", baseUrl);

  const headers = composeAuthHeaders(authCookies);

  const response = await fetch(url.toString(), {
    cache: "no-store",
    credentials: "include",
    headers,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<DatabaseStatus>;
}

export async function reloadDatabase(
  resource: ReloadResource,
  mode: ReloadMode = "upsert",
  authCookies?: string,
): Promise<ReloadRun[]> {
  const baseUrl = resolveBaseUrl();
  const endpoint = resource === "all" ? "/admin/db/reload" : `/admin/db/reload/${resource}`;
  const url = new URL(endpoint, baseUrl);

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...composeAuthHeaders(authCookies),
  };

  const response = await fetch(url.toString(), {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    headers,
    body: JSON.stringify({ mode }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  if (resource === "all") {
    return response.json() as Promise<ReloadRun[]>;
  }

  const payload = (await response.json()) as ReloadRun;
  return [payload];
}

export interface CampaignSummaryQuery {
  week?: string;
  user?: string;
}

export async function fetchCampaignSummary(
  query: CampaignSummaryQuery = {},
  authCookies?: string,
): Promise<CampaignSummaryResponse> {
  const baseUrl = resolveBaseUrl();
  const url = new URL("/api/campaign/summary", baseUrl);
  const params = new URLSearchParams();

  if (query.week && query.week !== "all") {
    params.set("week", query.week);
  } else if (query.week === "all") {
    params.set("week", "all");
  }

  if (query.user) {
    params.set("user", query.user);
  }

  const queryString = params.toString();
  if (queryString) {
    url.search = queryString;
  }

  const headers = composeAuthHeaders(authCookies);

  const response = await fetch(url.toString(), {
    cache: "no-store",
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<CampaignSummaryResponse>;
}

export async function uploadSubmissions(
  file: File,
  authCookies?: string,
): Promise<SubmissionReloadSummary> {
  const baseUrl = resolveBaseUrl();
  const url = new URL("/api/admin/reload/submissions", baseUrl);
  const formData = new FormData();
  formData.append("file", file);

  const headers = composeAuthHeaders(authCookies);

  const response = await fetch(url.toString(), {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    headers,
    body: formData,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<SubmissionReloadSummary>;
}
