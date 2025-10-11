import type { DashboardResponse, SortOption } from "../types/dashboard";

export interface DashboardQuery {
  sort_by?: SortOption;
  week?: number;
  challenge?: number;
  user_id?: string;
}

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

export async function fetchDashboard(
  query: DashboardQuery = {},
): Promise<DashboardResponse> {
  const baseUrl = resolveBaseUrl();
  const url = new URL("/dashboard", baseUrl);
  const params = new URLSearchParams();

  if (query.sort_by) params.set("sort_by", query.sort_by);
  if (query.week) params.set("week", String(query.week));
  if (query.challenge) params.set("challenge", String(query.challenge));
  if (query.user_id) params.set("user_id", query.user_id);

  if ([...params.keys()].length > 0) {
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
