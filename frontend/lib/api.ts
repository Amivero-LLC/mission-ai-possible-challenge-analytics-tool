import type { DashboardResponse, SortOption } from "../types/dashboard";

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
function resolveBaseUrl() {
  if (typeof window === "undefined") {
    return (
      process.env.API_BASE_URL ??
      process.env.NEXT_PUBLIC_API_BASE_URL ??
      "http://localhost:8000"
    );
  }
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
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
  const response = await fetch(url.toString(), { cache: "no-store" });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<DashboardResponse>;
}
