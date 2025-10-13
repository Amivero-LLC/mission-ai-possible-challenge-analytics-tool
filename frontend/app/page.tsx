import { fetchDashboard } from "../lib/api";
import DashboardContent from "../components/DashboardContent";

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
  const dashboard = await fetchDashboard();

  return (
    <main className="page-root">
      <DashboardContent initialData={dashboard} />
    </main>
  );
}
