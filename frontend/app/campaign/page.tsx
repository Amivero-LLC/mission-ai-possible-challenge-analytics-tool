import { cookies } from "next/headers";

import CampaignPage from "../../components/CampaignPage";
import { fetchCampaignSummary, resolveBaseUrl } from "../../lib/api";
import type { AuthUser } from "../../types/auth";
import type { CampaignSummaryResponse } from "../../types/campaign";

async function fetchIsAdmin(cookieHeader?: string): Promise<boolean> {
  try {
    const baseUrl = resolveBaseUrl();
    const url = new URL("/api/auth/me", baseUrl);
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (cookieHeader) {
      headers.Cookie = cookieHeader;
    }

    const response = await fetch(url.toString(), {
      cache: "no-store",
      credentials: "include",
      headers,
    });

    if (!response.ok) {
      return false;
    }

    const payload = (await response.json()) as AuthUser;
    return payload.role === "ADMIN";
  } catch {
    return false;
  }
}

export const dynamic = "force-dynamic";

export default async function Page() {
  const cookieStore = cookies();
  const serializedCookies = cookieStore
    .getAll()
    .map(({ name, value }) => `${name}=${value}`)
    .join("; ");
  const cookieHeader = serializedCookies || undefined;

  const summaryPromise: Promise<CampaignSummaryResponse | null> = fetchCampaignSummary({}, cookieHeader)
    .then((payload) => payload)
    .catch((error) => {
      console.log("[CampaignPage] Failed to fetch campaign summary on server:", error);
      return null;
    });

  const [summary, isAdmin] = await Promise.all([
    summaryPromise,
    fetchIsAdmin(cookieHeader),
  ]);

  return <CampaignPage initialSummary={summary ?? undefined} initialWeek="all" isAdmin={isAdmin} />;
}
