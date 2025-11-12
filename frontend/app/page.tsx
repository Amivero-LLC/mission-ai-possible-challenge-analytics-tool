import { cookies } from "next/headers";
import { fetchDashboard } from "../lib/api";
import DashboardWrapper from "../components/DashboardWrapper";

/**
 * Next.js server component that preloads the latest dashboard data.
 *
 * Returns:
 *   JSX.Element – hydrated layout shell with dashboard content.
 *
 * Notes:
 *   - Runs on the server, so `fetchDashboard` uses environment-configured API_BASE_URL.
 *   - For cross-domain deployments, this may fail since cookies are on different domains
 *   - Client-side auth check will redirect to login if needed
 */
export default async function HomePage() {
  let dashboard = null;

  try {
    const cookieHeader = cookies().toString();
    dashboard = await fetchDashboard({}, cookieHeader || undefined);
  } catch (error) {
    // Dashboard fetch failed (expected for cross-domain auth)
    // Client component will handle auth check and redirect
    console.log("[HomePage] Failed to fetch dashboard on server:", error);
  }

  return <DashboardWrapper initialData={dashboard} />;
}
