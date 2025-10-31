import { cookies } from "next/headers";
import { fetchDashboard } from "../lib/api";
import DashboardPage from "../components/DashboardPage";

/**
 * Next.js server component that preloads the latest dashboard data.
 *
 * Returns:
 *   JSX.Element – hydrated layout shell with dashboard content.
 *
 * Notes:
 *   - Runs on the server, so `fetchDashboard` uses environment-configured API_BASE_URL.
 *   - Rendering the dashboard on the server improves perceived load times since
 *     the initial payload is embedded in the HTML.
 */
export default async function HomePage() {
  const cookieHeader = cookies().toString();
  const dashboard = await fetchDashboard({}, cookieHeader || undefined);

  return <DashboardPage initialData={dashboard} />;
}
