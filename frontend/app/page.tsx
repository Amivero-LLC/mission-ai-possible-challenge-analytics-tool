import { fetchDashboard } from "../lib/api";
import DashboardContent from "../components/DashboardContent";

export default async function HomePage() {
  const dashboard = await fetchDashboard();

  return (
    <main className="page-root">
      <DashboardContent initialData={dashboard} />
    </main>
  );
}
