'use client';

import { useCallback, useState } from "react";
import { fetchDashboard } from "../lib/api";
import type { DashboardResponse, SortOption } from "../types/dashboard";

type TabKey = "overview" | "allchats" | "missions" | "models";

type FilterState = {
  sortBy: SortOption;
  week: string;
  challenge: string;
  user: string;
};

const tabs: Array<{ id: TabKey; label: string }> = [
  { id: "overview", label: "📊 Overview" },
  { id: "allchats", label: "💬 All Chats" },
  { id: "missions", label: "🎯 Missions" },
  { id: "models", label: "🤖 Models" },
];

const defaultFilters: FilterState = {
  sortBy: "completions",
  week: "",
  challenge: "",
  user: "",
};

interface Props {
  initialData: DashboardResponse;
}

function formatNumber(value: number) {
  return value.toLocaleString();
}

function formatPercent(value: number, fractionDigits = 1) {
  return `${value.toFixed(fractionDigits)}%`;
}

// Use a shared formatter so server/client renders stay in sync and avoid hydration mismatches.
const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: true,
  timeZone: "UTC",
});

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) {
    return value;
  }
  return dateTimeFormatter.format(date);
}

function formatChatPreview(content: DashboardResponse["all_chats"][number]["messages"]) {
  return content
    .map(
      (message) =>
        `${message.role ?? "unknown"}: ${(message.content ?? "").slice(0, 120)}${
          (message.content ?? "").length > 120 ? "…" : ""
        }`,
    )
    .join(" • ");
}

export default function DashboardContent({ initialData }: Props) {
  const [dashboard, setDashboard] = useState<DashboardResponse>(initialData);
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [filters, setFilters] = useState<FilterState>(defaultFilters);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFiltersChange = (key: keyof FilterState, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const resetFilters = useCallback(async () => {
    setFilters(defaultFilters);
    setError(null);
    setLoading(true);
    try {
      const data = await fetchDashboard({ sort_by: defaultFilters.sortBy });
      setDashboard(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to refresh dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  const applyFilters = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const data = await fetchDashboard({
        sort_by: filters.sortBy,
        week: filters.week ? Number(filters.week) : undefined,
        challenge: filters.challenge ? Number(filters.challenge) : undefined,
        user_id: filters.user || undefined,
      });
      setDashboard(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>🎯 Mission Challenge Dashboard</h1>
        <p className="dashboard-subtitle">OpenWebUI Employee Engagement Tracker</p>
        <p className="dashboard-timestamp">
          Last Updated: {formatDateTime(dashboard.generated_at)}
        </p>
      </header>

      <section className="stats-grid">
        <article className="stat-card">
          <p className="stat-label">Total Chats</p>
          <p className="stat-value">{formatNumber(dashboard.summary.total_chats)}</p>
          <p className="stat-sublabel">In System</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Mission Attempts</p>
          <p className="stat-value">{formatNumber(dashboard.summary.mission_attempts)}</p>
          <p className="stat-sublabel">Across All Missions</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Completions</p>
          <p className="stat-value">{formatNumber(dashboard.summary.mission_completions)}</p>
          <p className="stat-sublabel">
            {formatPercent(dashboard.summary.success_rate)} Success Rate
          </p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Participants</p>
          <p className="stat-value">{formatNumber(dashboard.summary.unique_users)}</p>
          <p className="stat-sublabel">
            {formatPercent(dashboard.summary.participation_rate)} Participation
          </p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Models Used</p>
          <p className="stat-value">{formatNumber(dashboard.model_stats.length)}</p>
          <p className="stat-sublabel">Unique Models</p>
        </article>
      </section>

      <section className="filters-panel">
        <div className="filter-group">
          <label className="filter-label" htmlFor="week-input">
            Week
          </label>
          <input
            id="week-input"
            className="filter-input"
            type="number"
            min={1}
            placeholder="All weeks"
            value={filters.week}
            onChange={(event) => handleFiltersChange("week", event.target.value)}
          />
        </div>
        <div className="filter-group">
          <label className="filter-label" htmlFor="challenge-input">
            Challenge
          </label>
          <input
            id="challenge-input"
            className="filter-input"
            type="number"
            min={1}
            placeholder="All challenges"
            value={filters.challenge}
            onChange={(event) => handleFiltersChange("challenge", event.target.value)}
          />
        </div>
        <div className="filter-group">
          <label className="filter-label" htmlFor="user-input">
            User ID
          </label>
          <input
            id="user-input"
            className="filter-input"
            type="text"
            placeholder="Filter by user"
            value={filters.user}
            onChange={(event) => handleFiltersChange("user", event.target.value)}
          />
        </div>
        <div className="filter-group">
          <label className="filter-label" htmlFor="sort-select">
            Leaderboard Sort
          </label>
          <select
            id="sort-select"
            className="filter-input"
            value={filters.sortBy}
            onChange={(event) =>
              handleFiltersChange("sortBy", event.target.value as SortOption)
            }
          >
            <option value="completions">Completions</option>
            <option value="attempts">Attempts</option>
            <option value="efficiency">Efficiency</option>
          </select>
        </div>
        <div className="filter-actions">
          <button
            className="filter-button"
            onClick={applyFilters}
            disabled={loading}
            type="button"
          >
            {loading ? "Applying..." : "Apply Filters"}
          </button>
          <button
            className="filter-button secondary"
            onClick={resetFilters}
            disabled={loading}
            type="button"
          >
            Reset
          </button>
        </div>
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      <nav className="tab-bar">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`tab-button ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <section className="tab-content">
        {activeTab === "overview" && (
          <div className="tab-section">
            {dashboard.summary.mission_attempts === 0 ? (
              <div className="no-data">
                <h2>🚀 No Mission Attempts Yet</h2>
                <p>The mission system is ready and waiting for employees to participate!</p>
                <p className="no-data-link">
                  https://amichat.prod.amivero-solutions.com/?model=maip---week-1---challenge-1
                </p>
              </div>
            ) : (
              <>
                <section className="section">
                  <h2 className="section-title">🏆 Leaderboard - Top Performers</h2>
                  <div className="table-wrapper">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Rank</th>
                          <th>User</th>
                          <th>Completions</th>
                          <th>Attempts</th>
                          <th>Success Rate</th>
                          <th>Messages</th>
                          <th>Unique Missions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboard.leaderboard.map((entry, index) => (
                          <tr key={entry.user_id}>
                            <td>{index + 1}</td>
                            <td>
                              <div className="user-cell">
                                <span className="badge badge-info">{entry.user_name}</span>
                                <span className="user-id">{entry.user_id.slice(0, 12)}…</span>
                              </div>
                            </td>
                            <td>{formatNumber(entry.completions)}</td>
                            <td>{formatNumber(entry.attempts)}</td>
                            <td>{formatPercent(entry.efficiency)}</td>
                            <td>{formatNumber(entry.total_messages)}</td>
                            <td>
                              <div className="badge-group">
                                <span className="badge badge-success">
                                  {entry.unique_missions_completed} completed
                                </span>
                                <span className="badge badge-warning">
                                  {entry.unique_missions_attempted} attempted
                                </span>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>

                <section className="section">
                  <h2 className="section-title">🎯 Mission Breakdown</h2>
                  {dashboard.mission_breakdown.length === 0 ? (
                    <p>No mission data available.</p>
                  ) : (
                    <div className="mission-grid">
                      {dashboard.mission_breakdown.map((mission) => (
                        <article key={mission.mission} className="mission-card">
                          <h3>{mission.mission}</h3>
                          <div className="mission-stats">
                            <div className="mission-stat">
                              <strong>Attempts:</strong> {formatNumber(mission.attempts)}
                            </div>
                            <div className="mission-stat">
                              <strong>Completions:</strong> {formatNumber(mission.completions)}
                            </div>
                            <div className="mission-stat">
                              <strong>Success Rate:</strong>{" "}
                              {formatPercent(mission.success_rate)}
                            </div>
                            <div className="mission-stat">
                              <strong>Unique Users:</strong>{" "}
                              {formatNumber(mission.unique_users)}
                            </div>
                          </div>
                          <div className="progress-bar">
                            <div
                              className="progress-fill"
                              style={{ width: `${Math.min(mission.success_rate, 100)}%` }}
                            >
                              {formatPercent(mission.success_rate, 0)} Success
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </section>
              </>
            )}
          </div>
        )}

        {activeTab === "allchats" && (
          <div className="tab-section">
            <section className="section">
              <h2 className="section-title">💬 All Chats</h2>
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Title</th>
                      <th>User</th>
                      <th>Model</th>
                      <th>Messages</th>
                      <th>Mission</th>
                      <th>Preview</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.all_chats.map((chat) => (
                      <tr key={chat.num}>
                        <td>{chat.num}</td>
                        <td>{chat.title}</td>
                        <td>
                          <div className="user-cell">
                            <span className="badge badge-info">{chat.user_name}</span>
                            <span className="user-id">{chat.user_id.slice(0, 12)}…</span>
                          </div>
                        </td>
                        <td>{chat.model}</td>
                        <td>{formatNumber(chat.message_count)}</td>
                        <td>
                          <span className={`badge ${chat.is_mission ? "badge-mission" : "badge-regular"}`}>
                            {chat.is_mission
                              ? chat.completed
                                ? "Mission ✓"
                                : "Mission"
                              : "Regular"}
                          </span>
                        </td>
                        <td className="chat-preview">
                          {chat.messages.length > 0 ? formatChatPreview(chat.messages) : "No preview"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}

        {activeTab === "missions" && (
          <div className="tab-section">
            <section className="section">
              <h2 className="section-title">🎯 Mission Details</h2>
              {dashboard.mission_breakdown.length === 0 ? (
                <p className="muted-text">No missions attempted yet.</p>
              ) : (
                dashboard.mission_breakdown.map((mission) => (
                  <article key={mission.mission} className="mission-detail-card">
                    <header>
                      <h3>{mission.mission}</h3>
                      <p>
                        {formatNumber(mission.completions)} / {formatNumber(mission.attempts)}{" "}
                        completions
                      </p>
                    </header>
                    <div className="mission-stats">
                      <div className="mission-stat">
                        <strong>Success Rate:</strong>{" "}
                        {formatPercent(mission.success_rate)}
                      </div>
                      <div className="mission-stat">
                        <strong>Unique Users:</strong>{" "}
                        {formatNumber(mission.unique_users)}
                      </div>
                    </div>
                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{ width: `${Math.min(mission.success_rate, 100)}%` }}
                      >
                        {formatPercent(mission.success_rate, 0)} Success
                      </div>
                    </div>
                  </article>
                ))
              )}
            </section>
          </div>
        )}

        {activeTab === "models" && (
          <div className="tab-section">
            <section className="section">
              <h2 className="section-title">🤖 Model Usage Statistics</h2>
              {dashboard.model_stats.length === 0 ? (
                <p className="muted-text">No model usage data available.</p>
              ) : (
                dashboard.model_stats.map((model) => (
                  <article key={model.model} className="model-card">
                    <h3>
                      <code>{model.model}</code>
                    </h3>
                    <div className="model-stats">
                      <div className="model-stat">
                        <strong>Total Chats:</strong> {formatNumber(model.total)}
                      </div>
                      <div className="model-stat">
                        <strong>Mission Chats:</strong> {formatNumber(model.mission)}
                      </div>
                      <div className="model-stat">
                        <strong>Completed Missions:</strong> {formatNumber(model.completed)}
                      </div>
                      <div className="model-stat">
                        <strong>Mission %:</strong> {formatPercent(model.mission_percentage)}
                      </div>
                    </div>
                  </article>
                ))
              )}
            </section>
          </div>
        )}
      </section>
    </div>
  );
}
