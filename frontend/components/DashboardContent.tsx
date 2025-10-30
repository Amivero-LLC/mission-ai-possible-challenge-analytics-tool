'use client';

import { useCallback, useEffect, useState } from "react";
import * as XLSX from "xlsx";
import { fetchDashboard, refreshData } from "../lib/api";
import type { DashboardResponse, SortOption, MissionDetail } from "../types/dashboard";

type TabKey = "overview" | "challengeresults" | "allchats" | "missions";

type FilterState = {
  week: string;
  challenge: string;
  user: string;
  status: string;
};

type ChatEntry = DashboardResponse["all_chats"][number];

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
  setExportCallbacks?: (callbacks: { onExportCSV: () => void; onExportExcel: () => void }) => void;
  setHeaderLoading?: (loading: boolean) => void;
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

// Fallback UTC formatters keep the initial SSR markup stable; client replaces them with locale-aware versions.
const defaultHeaderFormatter = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: true,
  timeZone: "UTC",
  timeZoneName: "short",
});

const defaultChatFormatter = new Intl.DateTimeFormat("en-US", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: true,
  timeZone: "UTC",
  timeZoneName: "short",
});

const defaultChallengeFormatter = new Intl.DateTimeFormat("en-US", {
  month: "2-digit",
  day: "2-digit",
  year: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: true,
  timeZone: "UTC",
  timeZoneName: "short",
});

type DateVariant = "header" | "chat" | "challenge";

function parseTimestamp(value?: string | number | null) {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  let timestamp: string | number = value;
  if (typeof value === "number") {
    timestamp = value < 1e12 ? value * 1000 : value;
  } else {
    const numericValue = Number(value);
    if (!Number.isNaN(numericValue) && numericValue > 0 && numericValue < 1e12) {
      timestamp = numericValue * 1000;
    }
  }

  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) {
    return null;
  }

  return date;
}

const variantDefaultFormatterMap: Record<DateVariant, Intl.DateTimeFormat> = {
  header: defaultHeaderFormatter,
  chat: defaultChatFormatter,
  challenge: defaultChallengeFormatter,
};

function formatTimestamp(
  value: string | number | null | undefined,
  variant: DateVariant,
  formatter?: Intl.DateTimeFormat
) {
  const parsedDate = parseTimestamp(value);
  if (!parsedDate) {
    return "N/A";
  }

  const activeFormatter = formatter ?? variantDefaultFormatterMap[variant];
  return activeFormatter.format(parsedDate);
}

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
function formatDateTime(value: string, formatter?: Intl.DateTimeFormat) {
  const formatted = formatTimestamp(value, "header", formatter);
  return formatted === "N/A" ? value : formatted;
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
function formatChatTimestamp(value?: string | number | null, formatter?: Intl.DateTimeFormat) {
  return formatTimestamp(value, "chat", formatter);
}

/**
 * Format challenge timestamp for display in tables
 */
function formatChallengeTimestamp(value?: string | number | null, formatter?: Intl.DateTimeFormat) {
  return formatTimestamp(value, "challenge", formatter);
}

/**
 * Render mission tooltip with incomplete, completed, and not started missions
 */
function renderMissionTooltip(
  incompleteDetails: MissionDetail[],
  completedDetails: MissionDetail[],
  notStartedDetails: MissionDetail[]
) {
  // Sort missions by week (nulls last) then by name
  const sortMissions = (missions: MissionDetail[]) => {
    return [...missions].sort((a, b) => {
      // Sort by week first (nulls last)
      if (a.week === null && b.week === null) {
        return a.name.localeCompare(b.name);
      }
      if (a.week === null) return 1;
      if (b.week === null) return -1;
      if (a.week !== b.week) {
        return a.week - b.week;
      }
      // Then by name
      return a.name.localeCompare(b.name);
    });
  };

  const sortedIncomplete = sortMissions(incompleteDetails);
  const sortedCompleted = sortMissions(completedDetails);
  const sortedNotStarted = sortMissions(notStartedDetails);

  return (
    <div className="mission-tooltip">
      <div className="mission-tooltip-header">Mission Details</div>

      <div className="mission-tooltip-section">
        <div className="mission-tooltip-section-title">
          Completed ({completedDetails.length})
        </div>
        <div className="mission-tooltip-list">
          {sortedCompleted.length > 0 ? (
            sortedCompleted.map((mission, idx) => (
              <div key={idx} className="mission-tooltip-item">
                <span className="mission-tooltip-week">
                  {mission.week !== null ? `Week ${mission.week}` : "N/A"}
                </span>
                <span className="mission-tooltip-name" title={mission.name}>
                  {mission.name}
                </span>
              </div>
            ))
          ) : (
            <div className="mission-tooltip-empty">No completed missions</div>
          )}
        </div>
      </div>

      <div className="mission-tooltip-section">
        <div className="mission-tooltip-section-title">
          Incomplete ({incompleteDetails.length})
        </div>
        <div className="mission-tooltip-list">
          {sortedIncomplete.length > 0 ? (
            sortedIncomplete.map((mission, idx) => (
              <div key={idx} className="mission-tooltip-item">
                <span className="mission-tooltip-week">
                  {mission.week !== null ? `Week ${mission.week}` : "N/A"}
                </span>
                <span className="mission-tooltip-name" title={mission.name}>
                  {mission.name}
                </span>
              </div>
            ))
          ) : (
            <div className="mission-tooltip-empty">No incomplete missions</div>
          )}
        </div>
      </div>

      <div className="mission-tooltip-section">
        <div className="mission-tooltip-section-title">
          Not Started ({notStartedDetails.length})
        </div>
        <div className="mission-tooltip-list">
          {sortedNotStarted.length > 0 ? (
            sortedNotStarted.map((mission, idx) => (
              <div key={idx} className="mission-tooltip-item">
                <span className="mission-tooltip-week">
                  {mission.week !== null ? `Week ${mission.week}` : "N/A"}
                </span>
                <span className="mission-tooltip-name" title={mission.name}>
                  {mission.name}
                </span>
              </div>
            ))
          ) : (
            <div className="mission-tooltip-empty">All missions started!</div>
          )}
        </div>
      </div>
    </div>
  );
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
export default function DashboardContent({ initialData, setExportCallbacks, setHeaderLoading }: Props) {
  const [dashboard, setDashboard] = useState<DashboardResponse>(initialData);
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [filters, setFilters] = useState<FilterState>(defaultFilters);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  const [selectedChat, setSelectedChat] = useState<ChatEntry | null>(null);
  const [headerFormatter, setHeaderFormatter] = useState<Intl.DateTimeFormat | null>(null);
  const [chatFormatter, setChatFormatter] = useState<Intl.DateTimeFormat | null>(null);
  const [challengeFormatter, setChallengeFormatter] = useState<Intl.DateTimeFormat | null>(null);

  // Challenge Results sorting state
  type ChallengeResultSortKey = "user_name" | "status" | "num_attempts" | "first_attempt_time" | "completed_time" | "num_messages";
  const [challengeResultSortKey, setChallengeResultSortKey] = useState<ChallengeResultSortKey>("user_name");
  const [challengeResultSortAsc, setChallengeResultSortAsc] = useState(true);

  // Leaderboard sorting state
  type LeaderboardSortKey = "user_name" | "completions" | "attempts" | "efficiency" | "total_messages" | "last_attempt" | "unique_missions_completed" | "unique_missions_attempted" | "total_points";
  const [leaderboardSortKey, setLeaderboardSortKey] = useState<LeaderboardSortKey>("completions");
  const [leaderboardSortAsc, setLeaderboardSortAsc] = useState(false);

  // All Chats sorting state
  type AllChatsSortKey = "num" | "week" | "user_name" | "challenge_name" | "created_at" | "message_count" | "completed";
  const [allChatsSortKey, setAllChatsSortKey] = useState<AllChatsSortKey>("created_at");
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
   * Manually refresh data from Open WebUI API.
   *
   * This triggers a fresh fetch from the Open WebUI API and updates the local cache.
   */
  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    setRefreshMessage(null);
    setError(null);
    try {
      const result = await refreshData();
      setRefreshMessage("Data refreshed successfully!");
      // After refresh, reload the dashboard with current filters
      const data = await fetchDashboard({
        sort_by: "completions",
        week: filters.week || undefined,
        challenge: filters.challenge || undefined,
        user_id: filters.user || undefined,
        status: filters.status || undefined,
      });
      setDashboard(data);
      // Clear success message after 3 seconds
      setTimeout(() => setRefreshMessage(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to refresh data from Open WebUI.");
    } finally {
      setRefreshing(false);
    }
  }, [filters]);

  /**
   * Automatically apply filters when filter state changes.
   */
  useEffect(() => {
    applyFilters();
  }, [applyFilters]);

  /**
   * Build locale-aware formatters once the component mounts on the client.
   */
  useEffect(() => {
    // Only run in browsers where Intl has full support
    try {
      setHeaderFormatter(
        new Intl.DateTimeFormat(undefined, {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: true,
          timeZoneName: "short",
        })
      );
      setChatFormatter(
        new Intl.DateTimeFormat(undefined, {
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          hour12: true,
          timeZoneName: "short",
        })
      );
      setChallengeFormatter(
        new Intl.DateTimeFormat(undefined, {
          month: "2-digit",
          day: "2-digit",
          year: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          hour12: true,
          timeZoneName: "short",
        })
      );
    } catch (err) {
      // Swallow errors from Intl constructor (very rare) and stick with UTC fallback.
      console.warn("Unable to build locale formatter", err);
    }
  }, []);

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
   * Provide export callbacks to header
   */
  useEffect(() => {
    if (setExportCallbacks) {
      setExportCallbacks({
        onExportCSV: exportToCSV,
        onExportExcel: exportToExcel,
      });
    }
  }, [setExportCallbacks, exportToCSV, exportToExcel]);

  /**
   * Sync loading state with header
   */
  useEffect(() => {
    if (setHeaderLoading) {
      setHeaderLoading(loading);
    }
  }, [loading, setHeaderLoading]);

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
    const direction = allChatsSortAsc ? 1 : -1;

    const normalizeTimestamp = (value: ChatEntry["created_at"]) => {
      if (value === null || value === undefined || value === "") {
        return direction === 1 ? Number.MAX_SAFE_INTEGER : Number.MIN_SAFE_INTEGER;
      }
      if (typeof value === "number") {
        return value < 1e12 ? value * 1000 : value;
      }
      const numericValue = Number(value);
      if (!Number.isNaN(numericValue) && numericValue > 0) {
        return numericValue < 1e12 ? numericValue * 1000 : numericValue;
      }
      const date = new Date(value);
      if (Number.isNaN(date.valueOf())) {
        return direction === 1 ? Number.MAX_SAFE_INTEGER : Number.MIN_SAFE_INTEGER;
      }
      return date.getTime();
    };

    chats.sort((a, b) => {
      switch (allChatsSortKey) {
        case "week": {
          const parseWeek = (value: typeof a.week) => {
            if (value === null || value === undefined || value === "") {
              return null;
            }
            const numericWeek = Number(value);
            return Number.isNaN(numericWeek) ? null : numericWeek;
          };
          const aWeek = parseWeek(a.week);
          const bWeek = parseWeek(b.week);
          if (aWeek === null && bWeek === null) return 0;
          if (aWeek === null) return 1;
          if (bWeek === null) return -1;
          return allChatsSortAsc ? aWeek - bWeek : bWeek - aWeek;
        }
        case "challenge_name": {
          const aName = (a.challenge_name ?? "").toString().toLowerCase();
          const bName = (b.challenge_name ?? "").toString().toLowerCase();
          if (!aName && !bName) return 0;
          if (!aName) return 1;
          if (!bName) return -1;
          return allChatsSortAsc ? aName.localeCompare(bName) : bName.localeCompare(aName);
        }
        case "created_at": {
          const aTime = normalizeTimestamp(a.created_at);
          const bTime = normalizeTimestamp(b.created_at);
          if (aTime === bTime) {
            return direction * (a.num - b.num);
          }
          return direction * (aTime - bTime);
        }
        case "completed": {
          const aCompleted = a.completed ? 1 : 0;
          const bCompleted = b.completed ? 1 : 0;
          if (aCompleted === bCompleted) {
            // Fall back to mission flag so completed missions sort ahead of regular chats.
            if (a.is_mission !== b.is_mission) {
              return direction * (a.is_mission ? -1 : 1);
            }
            return direction * (a.num - b.num);
          }
          return direction * (aCompleted - bCompleted);
        }
        default: {
          let aVal: unknown = (a as unknown as Record<string, unknown>)[allChatsSortKey];
          let bVal: unknown = (b as unknown as Record<string, unknown>)[allChatsSortKey];

          if (aVal === null || aVal === undefined) aVal = "";
          if (bVal === null || bVal === undefined) bVal = "";

          if (typeof aVal === "string" || typeof bVal === "string") {
            const aStr = String(aVal).toLowerCase();
            const bStr = String(bVal).toLowerCase();
            if (!aStr && !bStr) return 0;
            if (!aStr) return 1;
            if (!bStr) return -1;
            return allChatsSortAsc ? aStr.localeCompare(bStr) : bStr.localeCompare(aStr);
          }

          const aNum = Number(aVal) || 0;
          const bNum = Number(bVal) || 0;
          return direction * (aNum - bNum);
        }
      }
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

  const openChatModal = (chat: ChatEntry) => {
    setSelectedChat(chat);
  };

  const closeChatModal = () => {
    setSelectedChat(null);
  };

  const getWeekDisplay = (week: ChatEntry["week"]) => {
    if (week === null || week === undefined || week === "") {
      return "—";
    }
    return week;
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

      {/* Collapsible Sidebar */}
      <div
        style={{
          position: "fixed",
          bottom: "20px",
          right: sidebarCollapsed ? "-280px" : "20px",
          width: "280px",
          backgroundColor: "#ffffff",
          border: "1px solid #e5e7eb",
          borderRadius: "8px",
          boxShadow: "0 4px 6px rgba(0, 0, 0, 0.1)",
          zIndex: 1000,
          transition: "right 0.3s ease-in-out",
        }}
      >
        {/* Toggle Button */}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          style={{
            position: "absolute",
            left: "-40px",
            top: "50%",
            transform: "translateY(-50%)",
            width: "40px",
            height: "40px",
            backgroundColor: "#ffffff",
            border: "1px solid #e5e7eb",
            borderRight: "none",
            borderTopLeftRadius: "8px",
            borderBottomLeftRadius: "8px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "1.2rem",
            boxShadow: "-2px 2px 4px rgba(0, 0, 0, 0.05)",
          }}
        >
          {sidebarCollapsed ? "◀" : "▶"}
        </button>

        {/* Sidebar Content */}
        <div style={{ padding: "1.5rem" }}>
          <h3 style={{ margin: "0 0 1rem 0", fontSize: "1rem", fontWeight: "600", color: "#1f2937" }}>
            Data Status
          </h3>

          <div style={{ marginBottom: "1rem" }}>
            <p style={{ fontSize: "0.75rem", fontWeight: "600", color: "#6b7280", marginBottom: "0.25rem" }}>
              Last Updated
            </p>
            <p style={{ fontSize: "0.85rem", color: "#1f2937" }}>
              {formatDateTime(dashboard.generated_at, headerFormatter ?? undefined)}
            </p>
          </div>

          {dashboard.last_fetched && (
            <div style={{ marginBottom: "1.5rem" }}>
              <p style={{ fontSize: "0.75rem", fontWeight: "600", color: "#6b7280", marginBottom: "0.25rem" }}>
                Data Fetched
              </p>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <p style={{ fontSize: "0.85rem", color: "#1f2937", margin: 0 }}>
                  {formatDateTime(dashboard.last_fetched, headerFormatter ?? undefined)}
                </p>
                <span style={{ padding: "2px 8px", background: "rgba(102, 126, 234, 0.1)", borderRadius: "4px", fontSize: "0.7rem", fontWeight: "500" }}>
                  {dashboard.data_source === "api" ? "API" : "File"}
                </span>
              </div>
            </div>
          )}

          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="filter-button"
            style={{
              width: "100%",
              margin: 0,
              padding: "0.75rem",
              fontSize: "0.9rem",
            }}
          >
            {refreshing ? "⏳ Refreshing..." : "🔄 Refresh Data"}
          </button>

          {refreshMessage && (
            <p style={{
              color: "#10b981",
              fontSize: "0.8rem",
              marginTop: "0.75rem",
              padding: "8px 12px",
              background: "#d1fae5",
              borderRadius: "6px",
              margin: "0.75rem 0 0 0",
            }}>
              ✓ {refreshMessage}
            </p>
          )}
        </div>
      </div>

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
            <option value="not_attempted">Not Started</option>
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
                            onClick={() => handleLeaderboardSort("unique_missions_completed")}
                            style={{ cursor: "pointer" }}
                            title="Click to sort - Hover over badges for details"
                          >
                            Completed Missions {leaderboardSortKey === "unique_missions_completed" && (leaderboardSortAsc ? "↑" : "↓")} 👁️
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
                        </tr>
                      </thead>
                      <tbody>
                        {sortedLeaderboard().map((entry) => (
                          <tr key={entry.user_id}>
                            <td>
                              <span className="badge badge-info">{entry.user_name}</span>
                            </td>
                            <td>{formatNumber(entry.total_points)}</td>
                            <td>
                              <div className="mission-tooltip-container">
                                <div className="badge-group">
                                  <span className="badge badge-success">
                                    {entry.unique_missions_completed} completed
                                  </span>
                                  <span className="badge badge-warning">
                                    {entry.unique_missions_attempted} incomplete
                                  </span>
                                  <span className="badge badge-secondary">
                                    {entry.unique_missions_not_started} not started
                                  </span>
                                </div>
                                {renderMissionTooltip(
                                  entry.missions_attempted_details || [],
                                  entry.missions_completed_details || [],
                                  entry.missions_not_started_details || []
                                )}
                              </div>
                            </td>
                            <td>{formatNumber(entry.attempts)}</td>
                            <td>{formatPercent(entry.efficiency)}</td>
                            <td>{formatNumber(entry.total_messages)}</td>
                            <td>{formatChallengeTimestamp(entry.last_attempt, challengeFormatter ?? undefined)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
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
                        <div className="mission-metadata">
                          {selectedMission.week && <span className="metadata-item">Week {selectedMission.week}</span>}
                          {selectedMission.difficulty && <span className="metadata-item">Difficulty: {selectedMission.difficulty}</span>}
                          {selectedMission.points > 0 && <span className="metadata-item">Points: {selectedMission.points}</span>}
                        </div>
                        <div className="mission-stats">
                          <div className="mission-stat">
                            <strong>Attempted:</strong>{" "}
                            {formatNumber(selectedMission.users_attempted)}
                          </div>
                          <div className="mission-stat">
                            <strong>Completed:</strong>{" "}
                            {formatNumber(selectedMission.users_completed)}
                          </div>
                          <div className="mission-stat">
                            <strong>Not Started:</strong>{" "}
                            {formatNumber(selectedMission.users_not_started)}
                          </div>
                          <div className="mission-stat">
                            <strong>Success Rate:</strong>{" "}
                            {formatPercent(selectedMission.success_rate)}
                          </div>
                          <div className="mission-stat">
                            <strong>Avg Chats to Complete:</strong>{" "}
                            {selectedMission.avg_messages_to_complete.toFixed(1)}
                          </div>
                          <div className="mission-stat">
                            <strong>Avg Attempts to Complete:</strong>{" "}
                            {selectedMission.avg_attempts_to_complete.toFixed(1)}
                          </div>
                        </div>
                        <div className="progress-bar">
                          {(() => {
                            const totalUsers = selectedMission.users_attempted + selectedMission.users_not_started;
                            const completedPercent = totalUsers > 0 ? (selectedMission.users_completed / totalUsers) * 100 : 0;
                            const inProgressPercent = totalUsers > 0 ? ((selectedMission.users_attempted - selectedMission.users_completed) / totalUsers) * 100 : 0;

                            return (
                              <>
                                {completedPercent > 0 && (
                                  <div
                                    className="progress-segment completed"
                                    style={{ width: `${completedPercent}%` }}
                                  >
                                    {completedPercent >= 10 && (
                                      <span className="progress-label">
                                        {formatPercent(completedPercent, 0)} Completed
                                      </span>
                                    )}
                                  </div>
                                )}
                                {inProgressPercent > 0 && (
                                  <div
                                    className="progress-segment in-progress"
                                    style={{ width: `${inProgressPercent}%` }}
                                  >
                                    {inProgressPercent >= 10 && (
                                      <span className="progress-label">
                                        {formatPercent(inProgressPercent, 0)} In Progress
                                      </span>
                                    )}
                                  </div>
                                )}
                              </>
                            );
                          })()}
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
                              <td>{formatChallengeTimestamp(result.first_attempt_time, challengeFormatter ?? undefined)}</td>
                              <td>{formatChallengeTimestamp(result.completed_time, challengeFormatter ?? undefined)}</td>
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
                        onClick={() => handleAllChatsSort("week")}
                        style={{ cursor: "pointer" }}
                        title="Click to sort"
                      >
                        Week {allChatsSortKey === "week" && (allChatsSortAsc ? "↑" : "↓")}
                      </th>
                      <th
                        onClick={() => handleAllChatsSort("user_name")}
                        style={{ cursor: "pointer" }}
                        title="Click to sort"
                      >
                        User {allChatsSortKey === "user_name" && (allChatsSortAsc ? "↑" : "↓")}
                      </th>
                      <th
                        onClick={() => handleAllChatsSort("challenge_name")}
                        style={{ cursor: "pointer" }}
                        title="Click to sort"
                      >
                        Challenge {allChatsSortKey === "challenge_name" && (allChatsSortAsc ? "↑" : "↓")}
                      </th>
                      <th
                        onClick={() => handleAllChatsSort("created_at")}
                        style={{ cursor: "pointer" }}
                        title="Click to sort"
                      >
                        Start Date {allChatsSortKey === "created_at" && (allChatsSortAsc ? "↑" : "↓")}
                      </th>
                      <th
                        onClick={() => handleAllChatsSort("message_count")}
                        style={{ cursor: "pointer" }}
                        title="Click to sort"
                      >
                        Messages {allChatsSortKey === "message_count" && (allChatsSortAsc ? "↑" : "↓")}
                      </th>
                      <th
                        onClick={() => handleAllChatsSort("completed")}
                        style={{ cursor: "pointer" }}
                        title="Click to sort"
                      >
                        Result {allChatsSortKey === "completed" && (allChatsSortAsc ? "↑" : "↓")}
                      </th>
                      <th>Chat</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedAllChats().map((chat) => (
                      <tr key={chat.num}>
                        <td>{chat.num}</td>
                        <td>{getWeekDisplay(chat.week)}</td>
                        <td>
                          <span className="badge badge-info">{chat.user_name}</span>
                        </td>
                        <td>{chat.challenge_name || (chat.is_mission ? chat.model : "—")}</td>
                        <td>{formatChatTimestamp(chat.created_at, chatFormatter ?? undefined)}</td>
                        <td>{formatNumber(chat.message_count)}</td>
                        <td>
                          {chat.is_mission ? (
                            <span title={chat.completed ? "Completed" : "Not completed"}>
                              {chat.completed ? "✅" : "❌"}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td>
                          <button
                            type="button"
                            className="btn chat-open-btn"
                            onClick={() => openChatModal(chat)}
                          >
                            View
                          </button>
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
                [...dashboard.mission_breakdown]
                  .sort((a, b) => {
                    // Sort by week first
                    const weekA = Number(a.week) || 999;
                    const weekB = Number(b.week) || 999;
                    if (weekA !== weekB) {
                      return weekA - weekB;
                    }
                    // Then sort by mission name
                    return a.mission.localeCompare(b.mission);
                  })
                  .map((mission) => (
                  <article key={mission.mission} className="mission-detail-card">
                    <header>
                      <h3>{mission.mission}</h3>
                      <p>
                        {formatNumber(mission.completions)} / {formatNumber(mission.attempts)}{" "}
                        completions
                      </p>
                    </header>
                    <div className="mission-metadata">
                      {mission.week && <span className="metadata-item">Week {mission.week}</span>}
                      {mission.difficulty && <span className="metadata-item">Difficulty: {mission.difficulty}</span>}
                      {mission.points > 0 && <span className="metadata-item">Points: {mission.points}</span>}
                    </div>
                    <div className="mission-stats">
                      <div className="mission-stat">
                        <strong>Attempted:</strong>{" "}
                        {formatNumber(mission.users_attempted)}
                      </div>
                      <div className="mission-stat">
                        <strong>Completed:</strong>{" "}
                        {formatNumber(mission.users_completed)}
                      </div>
                      <div className="mission-stat">
                        <strong>Not Started:</strong>{" "}
                        {formatNumber(mission.users_not_started)}
                      </div>
                      <div className="mission-stat">
                        <strong>Success Rate:</strong>{" "}
                        {formatPercent(mission.success_rate)}
                      </div>
                      <div className="mission-stat">
                        <strong>Avg Chats to Complete:</strong>{" "}
                        {mission.avg_messages_to_complete.toFixed(1)}
                      </div>
                      <div className="mission-stat">
                        <strong>Avg Attempts to Complete:</strong>{" "}
                        {mission.avg_attempts_to_complete.toFixed(1)}
                      </div>
                    </div>
                    <div className="progress-bar">
                      {(() => {
                        const totalUsers = mission.users_attempted + mission.users_not_started;
                        const completedPercent = totalUsers > 0 ? (mission.users_completed / totalUsers) * 100 : 0;
                        const inProgressPercent = totalUsers > 0 ? ((mission.users_attempted - mission.users_completed) / totalUsers) * 100 : 0;

                        return (
                          <>
                            {completedPercent > 0 && (
                              <div
                                className="progress-segment completed"
                                style={{ width: `${completedPercent}%` }}
                              >
                                {completedPercent >= 10 && (
                                  <span className="progress-label">
                                    {formatPercent(completedPercent, 0)} Completed
                                  </span>
                                )}
                              </div>
                            )}
                            {inProgressPercent > 0 && (
                              <div
                                className="progress-segment in-progress"
                                style={{ width: `${inProgressPercent}%` }}
                              >
                                {inProgressPercent >= 10 && (
                                  <span className="progress-label">
                                    {formatPercent(inProgressPercent, 0)} In Progress
                                  </span>
                                )}
                              </div>
                            )}
                          </>
                        );
                      })()}
                    </div>
                  </article>
                ))
              )}
            </section>
          </div>
        )}
      </section>
      {selectedChat && (
        <div
          className="chat-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Chat transcript"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              closeChatModal();
            }
          }}
        >
          <div className="chat-modal" onClick={(event) => event.stopPropagation()}>
            <div className="chat-modal-header">
              <div className="chat-modal-title">
                <h3>
                  {selectedChat.challenge_name ||
                    (selectedChat.is_mission ? selectedChat.model : selectedChat.title) ||
                    `Chat #${selectedChat.num}`}
                </h3>
                <p>
                  👤 {selectedChat.user_name} ·{" "}
                  {selectedChat.is_mission ? `Week ${getWeekDisplay(selectedChat.week)}` : "Regular chat"}
                </p>
              </div>
              <button
                type="button"
                className="chat-modal-close"
                onClick={closeChatModal}
                aria-label="Close chat"
              >
                ×
              </button>
            </div>
            <div className="chat-modal-meta">
              <span>
                <strong>Start:</strong> {formatChatTimestamp(selectedChat.created_at, chatFormatter ?? undefined)}
              </span>
              <span>
                <strong>Messages:</strong> {formatNumber(selectedChat.message_count)}
              </span>
              <span>
                <strong>Result:</strong>{" "}
                {selectedChat.is_mission
                  ? selectedChat.completed
                    ? "✅ Completed"
                    : "❌ Not completed"
                  : "—"}
              </span>
            </div>
            <div className="chat-thread">
              {selectedChat.messages.length === 0 ? (
                <p className="chat-empty">No messages recorded for this chat.</p>
              ) : (
                selectedChat.messages.map((message, index) => {
                  const role = (message.role ?? "system").toLowerCase();
                  const isUser = role === "user";
                  const isAssistant = role === "assistant";
                  const timestampLabel = formatChatTimestamp(
                    message.timestamp ?? selectedChat.created_at,
                    chatFormatter ?? undefined,
                  );

                  let rowClass = "chat-message-row system";
                  let bubbleClass = "chat-bubble system";
                  if (isUser) {
                    rowClass = "chat-message-row user";
                    bubbleClass = "chat-bubble user";
                  } else if (isAssistant) {
                    rowClass = "chat-message-row assistant";
                    bubbleClass = "chat-bubble assistant";
                  }

                  return (
                    <div className={rowClass} key={`${selectedChat.num}-${index}`}>
                      <div className={bubbleClass}>
                        <div className="chat-bubble-content">
                          {message.content ? message.content : "(no content)"}
                        </div>
                        {timestampLabel !== "N/A" && (
                          <span className="chat-bubble-timestamp">{timestampLabel}</span>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
