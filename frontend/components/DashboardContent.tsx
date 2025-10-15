'use client';

import { useCallback, useState } from "react";
import * as XLSX from "xlsx";
import { fetchDashboard } from "../lib/api";
import type { DashboardResponse, SortOption } from "../types/dashboard";

type TabKey = "overview" | "allchats" | "missions" | "models";

type FilterState = {
  sortBy: SortOption;
  dateFrom: string;
  dateTo: string;
  challenge: string;
  user: string;
  status: string;
};

/**
 * UI tabs rendered by the dashboard. Keys align with conditional sections below.
 */
const tabs: Array<{ id: TabKey; label: string }> = [
  { id: "overview", label: "📊 Overview" },
  { id: "allchats", label: "💬 All Chats" },
  { id: "missions", label: "🎯 Missions" },
  { id: "models", label: "🤖 Models" },
];

const defaultFilters: FilterState = {
  sortBy: "completions",
  dateFrom: "",
  dateTo: "",
  challenge: "",
  user: "",
  status: "",
};

interface Props {
  initialData: DashboardResponse;
}

/**
 * Human-friendly number formatter that keeps locale-specific separators (e.g., 1,234).
 *
 * Args:
 *   value (number): Metric to render.
 *
 * Returns:
 *   string – Formatted number that matches browser locale defaults.
 */
function formatNumber(value: number) {
  return value.toLocaleString();
}

/**
 * Render percentages with a configurable precision.
 *
 * Args:
 *   value (number): Value expected between 0–100, but no guard is enforced so callers
 *     can intentionally display >100% when required.
 *   fractionDigits (number): Number of digits after the decimal point (default 1).
 *
 * Returns:
 *   string in the format "12.3%".
 */
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

/**
 * Format ISO timestamps for display in the dashboard header.
 *
 * Args:
 *   value (string): ISO-8601 timestamp returned by the API.
 *
 * Returns:
 *   string – Locale-aware date/time. Invalid inputs fall back to the raw value so
 *   developers can spot malformed data.
 */
function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) {
    return value;
  }
  return dateTimeFormatter.format(date);
}

/**
 * Format chat timestamps that may be Unix timestamps (numbers) or ISO strings.
 *
 * Args:
 *   value (string | number | null | undefined): Timestamp from chat data.
 *
 * Returns:
 *   string – Formatted date/time or "N/A" if unavailable.
 */
function formatChatTimestamp(value?: string | number | null) {
  if (!value) return "N/A";
  
  // If it's a Unix timestamp (number), convert to milliseconds
  const timestamp = typeof value === "number" ? value * 1000 : value;
  const date = new Date(timestamp);
  
  if (Number.isNaN(date.valueOf())) {
    return "N/A";
  }
  
  return dateTimeFormatter.format(date);
}

/**
 * Creates a short inline preview of a chat by concatenating message snippets.
 *
 * Args:
 *   content (Array<{ role?: string | null; content?: string | null }>): Chat messages.
 *
 * Returns:
 *   string – Messages joined with separators, truncated to reduce table width.
 */
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

/**
 * Mission dashboard client component.
 *
+ Purpose:
 *   - Maintains filter state and dispatches requests to refresh mission analytics.
 *   - Renders tabbed views for overview metrics, raw chats, mission breakdown, and model usage.
 *
 * Props:
 *   initialData (DashboardResponse): Pre-fetched payload injected by the server component.
 *
 * State:
 *   - dashboard (DashboardResponse): Current dataset backing the UI.
 *   - activeTab (TabKey): Controls which section is visible.
 *   - filters (FilterState): Raw filter values entered by the user.
 *   - loading / error: Track asynchronous fetch status for inline messaging.
 *
 * Usage:
 *   <DashboardContent initialData={dashboard} />
 *
 * Side Effects:
 *   - Invokes `fetchDashboard` on filter changes, reading from the FastAPI backend.
 */
export default function DashboardContent({ initialData }: Props) {
  const [dashboard, setDashboard] = useState<DashboardResponse>(initialData);
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [filters, setFilters] = useState<FilterState>(defaultFilters);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFiltersChange = (key: keyof FilterState, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  /**
   * Restore default filters and reload the dashboard.
   *
   * Error Handling:
   *   - Catches network/HTTP failures and exposes the message in component state.
   */
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

  /**
   * Apply user-selected filters and request an updated dataset from the API.
   *
   * Notes:
   *   - Converts numeric inputs from `<select>` fields (strings) into numbers
   *     before calling `fetchDashboard` so query params remain accurate.
   */
  const applyFilters = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const data = await fetchDashboard({
        sort_by: filters.sortBy,
        date_from: filters.dateFrom || undefined,
        date_to: filters.dateTo || undefined,
        challenge: filters.challenge || undefined,
        user_id: filters.user || undefined,
        status: filters.status || undefined,
      });
      setDashboard(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  /**
   * Export current tab data to CSV format
   */
  const exportToCSV = useCallback(() => {
    let data: any[] = [];
    let filename = "";

    switch (activeTab) {
      case "overview":
        // Export leaderboard data
        data = dashboard.leaderboard.map((entry, index) => ({
          Rank: index + 1,
          "User Name": entry.user_name,
          Completions: entry.completions,
          Attempts: entry.attempts,
          "Success Rate": `${entry.efficiency.toFixed(1)}%`,
          Messages: entry.total_messages,
          "Last Activity": formatChatTimestamp(entry.last_attempt),
          "Unique Missions Completed": entry.unique_missions_completed,
          "Unique Missions Attempted": entry.unique_missions_attempted,
        }));
        filename = "leaderboard.csv";
        break;

      case "allchats":
        // Export all chats data
        data = dashboard.all_chats.map((chat) => ({
          "#": chat.num,
          Title: chat.title,
          "User Name": chat.user_name,
          Model: chat.model,
          "Created At": formatChatTimestamp(chat.created_at),
          Messages: chat.message_count,
          Mission: chat.is_mission ? (chat.completed ? "Mission ✓" : "Mission") : "Regular",
        }));
        filename = "all_chats.csv";
        break;

      case "missions":
        // Export missions data
        data = dashboard.mission_breakdown.map((mission) => ({
          Mission: mission.mission,
          Attempts: mission.attempts,
          Completions: mission.completions,
          "Success Rate": `${mission.success_rate.toFixed(1)}%`,
          "Unique Users": mission.unique_users,
        }));
        filename = "missions.csv";
        break;

      case "models":
        // Export models data
        data = dashboard.model_stats.map((model) => ({
          Model: model.model,
          "Total Chats": model.total,
          "Mission Chats": model.mission,
          "Completed Missions": model.completed,
          "Mission %": `${model.mission_percentage.toFixed(1)}%`,
        }));
        filename = "models.csv";
        break;
    }

    if (data.length === 0) return;

    // Convert to CSV
    const headers = Object.keys(data[0]);
    const csvContent = [
      headers.join(","),
      ...data.map((row) =>
        headers.map((header) => {
          const value = row[header];
          // Escape quotes and wrap in quotes if contains comma
          const stringValue = String(value ?? "");
          return stringValue.includes(",") || stringValue.includes('"')
            ? `"${stringValue.replace(/"/g, '""')}"`
            : stringValue;
        }).join(",")
      ),
    ].join("\n");

    // Download
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  }, [activeTab, dashboard]);

  /**
   * Export current tab data to Excel format
   */
  const exportToExcel = useCallback(() => {
    let data: any[] = [];
    let sheetName = "";
    let filename = "";

    switch (activeTab) {
      case "overview":
        data = dashboard.leaderboard.map((entry, index) => ({
          Rank: index + 1,
          "User Name": entry.user_name,
          Completions: entry.completions,
          Attempts: entry.attempts,
          "Success Rate (%)": Number(entry.efficiency.toFixed(1)),
          Messages: entry.total_messages,
          "Last Activity": formatChatTimestamp(entry.last_attempt),
          "Unique Missions Completed": entry.unique_missions_completed,
          "Unique Missions Attempted": entry.unique_missions_attempted,
        }));
        sheetName = "Leaderboard";
        filename = "leaderboard.xlsx";
        break;

      case "allchats":
        data = dashboard.all_chats.map((chat) => ({
          "#": chat.num,
          Title: chat.title,
          "User Name": chat.user_name,
          Model: chat.model,
          "Created At": formatChatTimestamp(chat.created_at),
          Messages: chat.message_count,
          Mission: chat.is_mission ? (chat.completed ? "Mission ✓" : "Mission") : "Regular",
        }));
        sheetName = "All Chats";
        filename = "all_chats.xlsx";
        break;

      case "missions":
        data = dashboard.mission_breakdown.map((mission) => ({
          Mission: mission.mission,
          Attempts: mission.attempts,
          Completions: mission.completions,
          "Success Rate (%)": Number(mission.success_rate.toFixed(1)),
          "Unique Users": mission.unique_users,
        }));
        sheetName = "Missions";
        filename = "missions.xlsx";
        break;

      case "models":
        data = dashboard.model_stats.map((model) => ({
          Model: model.model,
          "Total Chats": model.total,
          "Mission Chats": model.mission,
          "Completed Missions": model.completed,
          "Mission %": Number(model.mission_percentage.toFixed(1)),
        }));
        sheetName = "Models";
        filename = "models.xlsx";
        break;
    }

    if (data.length === 0) return;

    // Create workbook and worksheet
    const worksheet = XLSX.utils.json_to_sheet(data);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, sheetName);

    // Download
    XLSX.writeFile(workbook, filename);
  }, [activeTab, dashboard]);

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Amivero's Mission: AI Possible</h1>
        <p className="dashboard-subtitle">🎯 Mission Challenge Dashboard</p>
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
          <label className="filter-label" htmlFor="date-from-input">
            Date From
          </label>
          <input
            id="date-from-input"
            className="filter-input"
            type="date"
            value={filters.dateFrom}
            onChange={(event) => handleFiltersChange("dateFrom", event.target.value)}
          />
        </div>
        <div className="filter-group">
          <label className="filter-label" htmlFor="date-to-input">
            Date To
          </label>
          <input
            id="date-to-input"
            className="filter-input"
            type="date"
            value={filters.dateTo}
            onChange={(event) => handleFiltersChange("dateTo", event.target.value)}
          />
        </div>
        <div className="filter-group">
          <label className="filter-label" htmlFor="challenge-select">
            Challenge
          </label>
          <select
            id="challenge-select"
            className="filter-input"
            value={filters.challenge}
            onChange={(event) => handleFiltersChange("challenge", event.target.value)}
          >
            <option value="">All Challenges</option>
            {(dashboard.summary.missions_list || []).map((mission) => (
              <option key={mission} value={mission}>
                {mission}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label className="filter-label" htmlFor="status-select">
            Status
          </label>
          <select
            id="status-select"
            className="filter-input"
            value={filters.status}
            onChange={(event) => handleFiltersChange("status", event.target.value)}
          >
            <option value="">All</option>
            <option value="completed">Completed</option>
            <option value="attempted">In Progress</option>
          </select>
        </div>
        <div className="filter-group">
          <label className="filter-label" htmlFor="user-select">
            User Name
          </label>
          <select
            id="user-select"
            className="filter-input"
            value={filters.user}
            onChange={(event) => handleFiltersChange("user", event.target.value)}
          >
            <option value="">All Users</option>
            {(dashboard.summary.users_list || []).map((user) => (
              <option key={user.user_id} value={user.user_id}>
                {user.user_name}
              </option>
            ))}
          </select>
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
          <button
            className="filter-button secondary"
            onClick={exportToCSV}
            type="button"
            title="Export current tab to CSV"
          >
            📥 CSV
          </button>
          <button
            className="filter-button secondary"
            onClick={exportToExcel}
            type="button"
            title="Export current tab to Excel"
          >
            📥 Excel
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
                          <th>Last Activity</th>
                          <th>Unique Missions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboard.leaderboard.map((entry, index) => (
                          <tr key={entry.user_id}>
                            <td>{index + 1}</td>
                            <td>
                              <span className="badge badge-info">{entry.user_name}</span>
                            </td>
                            <td>{formatNumber(entry.completions)}</td>
                            <td>{formatNumber(entry.attempts)}</td>
                            <td>{formatPercent(entry.efficiency)}</td>
                            <td>{formatNumber(entry.total_messages)}</td>
                            <td>{formatChatTimestamp(entry.last_attempt)}</td>
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
                      <th>Created At</th>
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
                          <span className="badge badge-info">{chat.user_name}</span>
                        </td>
                        <td>{chat.model}</td>
                        <td>{formatChatTimestamp(chat.created_at)}</td>
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
