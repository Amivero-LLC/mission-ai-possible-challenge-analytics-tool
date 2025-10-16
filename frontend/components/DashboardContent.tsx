'use client';

import { useCallback, useEffect, useState } from "react";
import * as XLSX from "xlsx";
import { fetchDashboard } from "../lib/api";
import type { DashboardResponse, SortOption } from "../types/dashboard";

type TabKey = "overview" | "challengeresults" | "allchats" | "missions";

type FilterState = {
  week: string;
  challenge: string;
  user: string;
  status: string;
};

/**
 * UI tabs rendered by the dashboard. Keys align with conditional sections below.
 */
const tabs: Array<{ id: TabKey; label: string }> = [
  { id: "overview", label: "📊 Overview" },
  { id: "challengeresults", label: "🏅 Challenge Results" },
  { id: "allchats", label: "💬 All Chats" },
  { id: "missions", label: "🎯 Missions" },
];

const defaultFilters: FilterState = {
  week: "",
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

  // Challenge Results sorting state
  type ChallengeResultSortKey = "user_name" | "status" | "num_attempts" | "first_attempt_time" | "completed_time" | "num_messages";
  const [challengeResultSortKey, setChallengeResultSortKey] = useState<ChallengeResultSortKey>("status");
  const [challengeResultSortAsc, setChallengeResultSortAsc] = useState(true);

  // Leaderboard sorting state
  type LeaderboardSortKey = "user_name" | "completions" | "attempts" | "efficiency" | "total_messages" | "last_attempt" | "unique_missions_completed" | "unique_missions_attempted" | "total_points";
  const [leaderboardSortKey, setLeaderboardSortKey] = useState<LeaderboardSortKey>("completions");
  const [leaderboardSortAsc, setLeaderboardSortAsc] = useState(false);

  // All Chats sorting state
  type AllChatsSortKey = "num" | "title" | "user_name" | "model" | "created_at" | "message_count" | "is_mission";
  const [allChatsSortKey, setAllChatsSortKey] = useState<AllChatsSortKey>("num");
  const [allChatsSortAsc, setAllChatsSortAsc] = useState(false);

  const handleFiltersChange = (key: keyof FilterState, value: string) => {
    setFilters((prev) => {
      const newFilters = { ...prev, [key]: value };
      // Clear challenge filter when week changes
      if (key === "week") {
        newFilters.challenge = "";
      }
      return newFilters;
    });
  };

  /**
   * Filter missions list based on selected week
   */
  const filteredMissions = filters.week
    ? (dashboard.summary.missions_list || []).filter((mission) => {
        const missionWeek = dashboard.summary.missions_with_weeks?.[mission];
        return missionWeek === filters.week;
      })
    : dashboard.summary.missions_list || [];

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
      const data = await fetchDashboard({ sort_by: "completions" });
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
        sort_by: "completions",
        week: filters.week || undefined,
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
   * Automatically apply filters when filter state changes.
   */
  useEffect(() => {
    applyFilters();
  }, [applyFilters]);

  /**
   * Export current tab data to CSV format
   */
  const exportToCSV = useCallback(() => {
    // Use the new export_data format for all exports
    const data = dashboard.export_data.map((row) => ({
      "Name": row.user_name,
      "Email": row.email,
      "Challenge Name": row.challenge_name,
      "Status": row.status,
      "Completed": row.completed,
      "Number of Attempts": row.num_attempts,
      "Number of Messages": row.num_messages,
      "Week": row.week,
      "Difficulty": row.difficulty,
      "DateTime Started": row.datetime_started || "",
      "DateTime Completed": row.datetime_completed || "",
      "Points Earned": row.points_earned,
    }));

    if (data.length === 0) return;

    // Convert to CSV
    const headers = Object.keys(data[0]) as Array<keyof typeof data[0]>;
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
    link.download = "user_challenge_export.csv";
    link.click();
    URL.revokeObjectURL(link.href);
  }, [dashboard]);

  /**
   * Export current tab data to Excel format
   */
  const exportToExcel = useCallback(() => {
    // Use the new export_data format for all exports
    const data = dashboard.export_data.map((row) => ({
      "Name": row.user_name,
      "Email": row.email,
      "Challenge Name": row.challenge_name,
      "Status": row.status,
      "Completed": row.completed,
      "Number of Attempts": row.num_attempts,
      "Number of Messages": row.num_messages,
      "Week": row.week,
      "Difficulty": row.difficulty,
      "DateTime Started": row.datetime_started || "",
      "DateTime Completed": row.datetime_completed || "",
      "Points Earned": row.points_earned,
    }));

    if (data.length === 0) return;

    // Create workbook and worksheet
    const worksheet = XLSX.utils.json_to_sheet(data);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "User Challenge Export");

    // Download
    XLSX.writeFile(workbook, "user_challenge_export.xlsx");
  }, [dashboard]);

  /**
   * Sort challenge results based on the current sort key and direction
   */
  const sortedChallengeResults = useCallback(() => {
    if (!dashboard.challenge_results || dashboard.challenge_results.length === 0) {
      return [];
    }

    const results = [...dashboard.challenge_results];

    results.sort((a, b) => {
      let aVal: any = a[challengeResultSortKey];
      let bVal: any = b[challengeResultSortKey];

      // Handle null/undefined values
      if (aVal === null || aVal === undefined) aVal = "";
      if (bVal === null || bVal === undefined) bVal = "";

      // For timestamps, convert to numbers for proper sorting
      if (challengeResultSortKey === "first_attempt_time" || challengeResultSortKey === "completed_time") {
        aVal = typeof aVal === "number" ? aVal : (aVal ? new Date(aVal).getTime() : 0);
        bVal = typeof bVal === "number" ? bVal : (bVal ? new Date(bVal).getTime() : 0);
      }

      // For strings, use locale compare
      if (typeof aVal === "string" && typeof bVal === "string") {
        return challengeResultSortAsc
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      // For numbers
      return challengeResultSortAsc ? aVal - bVal : bVal - aVal;
    });

    return results;
  }, [dashboard.challenge_results, challengeResultSortKey, challengeResultSortAsc]);

  /**
   * Handle column header click for sorting
   */
  const handleChallengeResultSort = (key: ChallengeResultSortKey) => {
    if (challengeResultSortKey === key) {
      // Toggle direction if clicking the same column
      setChallengeResultSortAsc(!challengeResultSortAsc);
    } else {
      // Set new sort key and default to ascending
      setChallengeResultSortKey(key);
      setChallengeResultSortAsc(true);
    }
  };

  /**
   * Sort leaderboard based on the current sort key and direction
   */
  const sortedLeaderboard = useCallback(() => {
    if (!dashboard.leaderboard || dashboard.leaderboard.length === 0) {
      return [];
    }

    const leaderboard = [...dashboard.leaderboard];

    leaderboard.sort((a, b) => {
      let aVal: any = a[leaderboardSortKey];
      let bVal: any = b[leaderboardSortKey];

      // Handle null/undefined values
      if (aVal === null || aVal === undefined) aVal = "";
      if (bVal === null || bVal === undefined) bVal = "";

      // For timestamps, convert to numbers for proper sorting
      if (leaderboardSortKey === "last_attempt") {
        aVal = typeof aVal === "number" ? aVal : (aVal ? new Date(aVal).getTime() : 0);
        bVal = typeof bVal === "number" ? bVal : (bVal ? new Date(bVal).getTime() : 0);
      }

      // For strings, use locale compare
      if (typeof aVal === "string" && typeof bVal === "string") {
        return leaderboardSortAsc
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      // For numbers
      return leaderboardSortAsc ? aVal - bVal : bVal - aVal;
    });

    return leaderboard;
  }, [dashboard.leaderboard, leaderboardSortKey, leaderboardSortAsc]);

  /**
   * Handle column header click for leaderboard sorting
   */
  const handleLeaderboardSort = (key: LeaderboardSortKey) => {
    if (leaderboardSortKey === key) {
      // Toggle direction if clicking the same column
      setLeaderboardSortAsc(!leaderboardSortAsc);
    } else {
      // Set new sort key and default to ascending
      setLeaderboardSortKey(key);
      setLeaderboardSortAsc(true);
    }
  };

  /**
   * Sort all chats based on the current sort key and direction
   */
  const sortedAllChats = useCallback(() => {
    if (!dashboard.all_chats || dashboard.all_chats.length === 0) {
      return [];
    }

    const chats = [...dashboard.all_chats];

    chats.sort((a, b) => {
      let aVal: any;
      let bVal: any;

      // Handle special case for is_mission (mission status)
      if (allChatsSortKey === "is_mission") {
        aVal = a.is_mission ? (a.completed ? 2 : 1) : 0;
        bVal = b.is_mission ? (b.completed ? 2 : 1) : 0;
      } else {
        aVal = a[allChatsSortKey];
        bVal = b[allChatsSortKey];
      }

      // Handle null/undefined values
      if (aVal === null || aVal === undefined) aVal = "";
      if (bVal === null || bVal === undefined) bVal = "";

      // For timestamps, convert to numbers for proper sorting
      if (allChatsSortKey === "created_at") {
        aVal = typeof aVal === "number" ? aVal : (aVal ? new Date(aVal).getTime() : 0);
        bVal = typeof bVal === "number" ? bVal : (bVal ? new Date(bVal).getTime() : 0);
      }

      // For strings, use locale compare
      if (typeof aVal === "string" && typeof bVal === "string") {
        return allChatsSortAsc
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      // For numbers
      return allChatsSortAsc ? aVal - bVal : bVal - aVal;
    });

    return chats;
  }, [dashboard.all_chats, allChatsSortKey, allChatsSortAsc]);

  /**
   * Handle column header click for all chats sorting
   */
  const handleAllChatsSort = (key: AllChatsSortKey) => {
    if (allChatsSortKey === key) {
      // Toggle direction if clicking the same column
      setAllChatsSortAsc(!allChatsSortAsc);
    } else {
      // Set new sort key and default to ascending
      setAllChatsSortKey(key);
      setAllChatsSortAsc(true);
    }
  };

  /**
   * Format timestamp for Challenge Results (EST timezone)
   */
  const formatChallengeTimestamp = (value?: string | number | null) => {
    if (!value) return "N/A";

    // If it's a Unix timestamp (number), convert to milliseconds
    const timestamp = typeof value === "number" ? value * 1000 : value;
    const date = new Date(timestamp);

    if (Number.isNaN(date.valueOf())) {
      return "N/A";
    }

    // Format as MM/DD/YY HH:MM EST
    const estFormatter = new Intl.DateTimeFormat("en-US", {
      month: "2-digit",
      day: "2-digit",
      year: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "America/New_York",
      hour12: true,
    });

    return estFormatter.format(date) + " EST";
  };

  /**
   * Get status badge class name
   */
  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case "Completed":
        return "badge badge-success";
      case "Attempted":
        return "badge badge-warning";
      default:
        return "badge badge-info";
    }
  };

  return (
    <div className="dashboard-container" style={{ position: "relative" }}>
      {/* Loading Overlay */}
      {loading && (
        <>
          <style dangerouslySetInnerHTML={{
            __html: `
              @keyframes dashboardSpinner {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
              }
            `
          }} />
          <div
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: "rgba(0, 0, 0, 0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 9999,
            }}
          >
            <div
              style={{
                width: "60px",
                height: "60px",
                border: "5px solid #f3f3f3",
                borderTop: "5px solid #3498db",
                borderRadius: "50%",
                animation: "dashboardSpinner 1s linear infinite",
              }}
            />
          </div>
        </>
      )}

      <header className="dashboard-header">
        <h1>Amivero&apos;s Mission: AI Possible</h1>
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
      </section>

      <section className="filters-panel">
        <div className="filter-group">
          <label className="filter-label" htmlFor="week-select">
            Select Week
          </label>
          <select
            id="week-select"
            className="filter-input"
            value={filters.week}
            onChange={(event) => handleFiltersChange("week", event.target.value)}
            disabled={loading}
          >
            <option value="">All Weeks</option>
            <option value="1">Week 1</option>
            <option value="2">Week 2</option>
            <option value="3">Week 3</option>
            <option value="4">Week 4</option>
            <option value="5">Week 5</option>
            <option value="6">Week 6</option>
            <option value="7">Week 7</option>
            <option value="8">Week 8</option>
            <option value="9">Week 9</option>
            <option value="10">Week 10</option>
          </select>
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
            disabled={loading}
          >
            <option value="">All Challenges</option>
            {filteredMissions.map((mission) => (
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
            disabled={loading}
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
            disabled={loading}
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
          <button
            className="filter-button secondary"
            onClick={resetFilters}
            disabled={loading}
            type="button"
            style={{ marginTop: "1.5rem" }}
          >
            Reset
          </button>
        </div>
      </section>

      <section className="filters-panel" style={{ marginTop: "1rem" }}>
        <h3 style={{ marginBottom: "1rem", fontSize: "1.1rem", fontWeight: "600" }}>
          Export Results
        </h3>
        <div className="filter-actions">
          <button
            className="filter-button secondary"
            onClick={exportToCSV}
            disabled={loading}
            type="button"
            title="Export current tab to CSV"
          >
            📥 CSV
          </button>
          <button
            className="filter-button secondary"
            onClick={exportToExcel}
            disabled={loading}
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
            disabled={loading}
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
                          <th
                            onClick={() => handleLeaderboardSort("user_name")}
                            style={{ cursor: "pointer" }}
                            title="Click to sort"
                          >
                            User {leaderboardSortKey === "user_name" && (leaderboardSortAsc ? "↑" : "↓")}
                          </th>
                          <th
                            onClick={() => handleLeaderboardSort("total_points")}
                            style={{ cursor: "pointer" }}
                            title="Click to sort"
                          >
                            Total Points {leaderboardSortKey === "total_points" && (leaderboardSortAsc ? "↑" : "↓")}
                          </th>
                          <th
                            onClick={() => handleLeaderboardSort("completions")}
                            style={{ cursor: "pointer" }}
                            title="Click to sort"
                          >
                            Completions {leaderboardSortKey === "completions" && (leaderboardSortAsc ? "↑" : "↓")}
                          </th>
                          <th
                            onClick={() => handleLeaderboardSort("attempts")}
                            style={{ cursor: "pointer" }}
                            title="Click to sort"
                          >
                            Attempts {leaderboardSortKey === "attempts" && (leaderboardSortAsc ? "↑" : "↓")}
                          </th>
                          <th
                            onClick={() => handleLeaderboardSort("efficiency")}
                            style={{ cursor: "pointer" }}
                            title="Click to sort"
                          >
                            Success Rate {leaderboardSortKey === "efficiency" && (leaderboardSortAsc ? "↑" : "↓")}
                          </th>
                          <th
                            onClick={() => handleLeaderboardSort("total_messages")}
                            style={{ cursor: "pointer" }}
                            title="Click to sort"
                          >
                            Messages {leaderboardSortKey === "total_messages" && (leaderboardSortAsc ? "↑" : "↓")}
                          </th>
                          <th
                            onClick={() => handleLeaderboardSort("last_attempt")}
                            style={{ cursor: "pointer" }}
                            title="Click to sort"
                          >
                            Last Activity {leaderboardSortKey === "last_attempt" && (leaderboardSortAsc ? "↑" : "↓")}
                          </th>
                          <th
                            onClick={() => handleLeaderboardSort("unique_missions_completed")}
                            style={{ cursor: "pointer" }}
                            title="Click to sort"
                          >
                            Unique Missions {leaderboardSortKey === "unique_missions_completed" && (leaderboardSortAsc ? "↑" : "↓")}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedLeaderboard().map((entry) => (
                          <tr key={entry.user_id}>
                            <td>
                              <span className="badge badge-info">{entry.user_name}</span>
                            </td>
                            <td>{formatNumber(entry.total_points)}</td>
                            <td>{formatNumber(entry.completions)}</td>
                            <td>{formatNumber(entry.attempts)}</td>
                            <td>{formatPercent(entry.efficiency)}</td>
                            <td>{formatNumber(entry.total_messages)}</td>
                            <td>{formatChallengeTimestamp(entry.last_attempt)}</td>
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

        {activeTab === "challengeresults" && (
          <div className="tab-section">
            {!filters.challenge ? (
              <div className="no-data">
                <p>Please select a specific challenge from the Challenge filter to view results.</p>
              </div>
            ) : (
              <>
                {/* Mission Detail Panel */}
                {(() => {
                  const selectedMission = dashboard.mission_breakdown.find(
                    (m) => m.mission === filters.challenge
                  );
                  return selectedMission ? (
                    <section className="section">
                      <h2 className="section-title">🎯 Mission Details</h2>
                      <article className="mission-detail-card">
                        <header>
                          <h3>{selectedMission.mission}</h3>
                          <p>
                            {formatNumber(selectedMission.completions)} /{" "}
                            {formatNumber(selectedMission.attempts)} completions
                          </p>
                        </header>
                        <div className="mission-stats">
                          <div className="mission-stat">
                            <strong>Success Rate:</strong>{" "}
                            {formatPercent(selectedMission.success_rate)}
                          </div>
                          <div className="mission-stat">
                            <strong>Unique Users:</strong>{" "}
                            {formatNumber(selectedMission.unique_users)}
                          </div>
                        </div>
                        <div className="progress-bar">
                          <div
                            className="progress-fill"
                            style={{
                              width: `${Math.min(selectedMission.success_rate, 100)}%`,
                            }}
                          >
                            {formatPercent(selectedMission.success_rate, 0)} Success
                          </div>
                        </div>
                      </article>
                    </section>
                  ) : null;
                })()}

                {/* Challenge Results Table */}
                <section className="section">
                  <h2 className="section-title">🏅 Challenge Results</h2>
                  {dashboard.challenge_results.length === 0 ? (
                    <div className="no-data">
                      <p>No results found for the selected challenge.</p>
                    </div>
                  ) : (
                    <div className="table-wrapper">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th
                              onClick={() => handleChallengeResultSort("user_name")}
                              style={{ cursor: "pointer" }}
                              title="Click to sort"
                            >
                              👤 User {challengeResultSortKey === "user_name" && (challengeResultSortAsc ? "↑" : "↓")}
                            </th>
                            <th
                              onClick={() => handleChallengeResultSort("status")}
                              style={{ cursor: "pointer" }}
                              title="Click to sort"
                            >
                              ✅ Status {challengeResultSortKey === "status" && (challengeResultSortAsc ? "↑" : "↓")}
                            </th>
                            <th
                              onClick={() => handleChallengeResultSort("num_attempts")}
                              style={{ cursor: "pointer" }}
                              title="Click to sort"
                            >
                              🔢 Attempts {challengeResultSortKey === "num_attempts" && (challengeResultSortAsc ? "↑" : "↓")}
                            </th>
                            <th
                              onClick={() => handleChallengeResultSort("first_attempt_time")}
                              style={{ cursor: "pointer" }}
                              title="Click to sort"
                            >
                              🚀 First Attempt {challengeResultSortKey === "first_attempt_time" && (challengeResultSortAsc ? "↑" : "↓")}
                            </th>
                            <th
                              onClick={() => handleChallengeResultSort("completed_time")}
                              style={{ cursor: "pointer" }}
                              title="Click to sort"
                            >
                              🏁 Completed {challengeResultSortKey === "completed_time" && (challengeResultSortAsc ? "↑" : "↓")}
                            </th>
                            <th
                              onClick={() => handleChallengeResultSort("num_messages")}
                              style={{ cursor: "pointer" }}
                              title="Click to sort"
                            >
                              💬 Messages {challengeResultSortKey === "num_messages" && (challengeResultSortAsc ? "↑" : "↓")}
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {sortedChallengeResults().map((result, index) => (
                            <tr key={`${result.user_id}-${index}`}>
                              <td>
                                <span className="badge badge-info">{result.user_name}</span>
                              </td>
                              <td>
                                {result.status && (
                                  <span className={getStatusBadgeClass(result.status)}>
                                    {result.status === "Completed" && "✓ "}
                                    {result.status}
                                  </span>
                                )}
                              </td>
                              <td>{formatNumber(result.num_attempts)}</td>
                              <td>{formatChallengeTimestamp(result.first_attempt_time)}</td>
                              <td>{formatChallengeTimestamp(result.completed_time)}</td>
                              <td>{formatNumber(result.num_messages)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
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
                      <th
                        onClick={() => handleAllChatsSort("num")}
                        style={{ cursor: "pointer" }}
                        title="Click to sort"
                      >
                        # {allChatsSortKey === "num" && (allChatsSortAsc ? "↑" : "↓")}
                      </th>
                      <th
                        onClick={() => handleAllChatsSort("title")}
                        style={{ cursor: "pointer" }}
                        title="Click to sort"
                      >
                        Title {allChatsSortKey === "title" && (allChatsSortAsc ? "↑" : "↓")}
                      </th>
                      <th
                        onClick={() => handleAllChatsSort("user_name")}
                        style={{ cursor: "pointer" }}
                        title="Click to sort"
                      >
                        User {allChatsSortKey === "user_name" && (allChatsSortAsc ? "↑" : "↓")}
                      </th>
                      <th
                        onClick={() => handleAllChatsSort("model")}
                        style={{ cursor: "pointer" }}
                        title="Click to sort"
                      >
                        Model {allChatsSortKey === "model" && (allChatsSortAsc ? "↑" : "↓")}
                      </th>
                      <th
                        onClick={() => handleAllChatsSort("created_at")}
                        style={{ cursor: "pointer" }}
                        title="Click to sort"
                      >
                        Created At {allChatsSortKey === "created_at" && (allChatsSortAsc ? "↑" : "↓")}
                      </th>
                      <th
                        onClick={() => handleAllChatsSort("message_count")}
                        style={{ cursor: "pointer" }}
                        title="Click to sort"
                      >
                        Messages {allChatsSortKey === "message_count" && (allChatsSortAsc ? "↑" : "↓")}
                      </th>
                      <th
                        onClick={() => handleAllChatsSort("is_mission")}
                        style={{ cursor: "pointer" }}
                        title="Click to sort"
                      >
                        Mission {allChatsSortKey === "is_mission" && (allChatsSortAsc ? "↑" : "↓")}
                      </th>
                      <th>Preview</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedAllChats().map((chat) => (
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
      </section>
    </div>
  );
}
