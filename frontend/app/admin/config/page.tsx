'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import AdminNavigation from "../../../components/AdminNavigation";
import Header from "../../../components/Header";
import { fetchDatabaseStatus, reloadDatabase } from "../../../lib/api";
import { toast } from "../../../lib/toast";
import type { DatabaseStatus, ReloadMode, ReloadRun, ReloadResource } from "../../../types/admin";

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

type DateVariant = "header";

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
};

function formatTimestamp(
  value: string | number | null | undefined,
  variant: DateVariant,
  formatter?: Intl.DateTimeFormat,
) {
  const parsedDate = parseTimestamp(value);
  if (!parsedDate) {
    return "N/A";
  }

  const activeFormatter = formatter ?? variantDefaultFormatterMap[variant];
  return activeFormatter.format(parsedDate);
}

function formatDateTime(value: string, formatter?: Intl.DateTimeFormat) {
  const formatted = formatTimestamp(value, "header", formatter);
  return formatted === "N/A" ? value : formatted;
}

function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "0";
  }
  return value.toLocaleString();
}

export default function AdminConfigPage() {
  const [adminStatus, setAdminStatus] = useState<DatabaseStatus | null>(null);
  const [adminLoading, setAdminLoading] = useState(false);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [reloadMode, setReloadMode] = useState<ReloadMode>("upsert");
  const [lastReloadRuns, setLastReloadRuns] = useState<ReloadRun[]>([]);
  const [headerFormatter, setHeaderFormatter] = useState<Intl.DateTimeFormat | null>(null);
  const lastReloadTimerRef = useRef<NodeJS.Timeout | null>(null);

  const summarizeRuns = useCallback(
    (runs: ReloadRun[], scope: ReloadResource | "all" | null = null): { message: string; variant: "success" | "default" } => {
      if (!runs || runs.length === 0) {
        return { message: "Data synchronized.", variant: "default" };
      }

      const trackedResources: ReloadResource[] = ["users", "models", "chats"];
      const newCounts: Record<string, number> = { users: 0, models: 0, chats: 0 };
      const totalCounts: Record<string, number | null> = { users: null, models: null, chats: null };

      runs.forEach((run) => {
        const resource = run.resource as ReloadResource;
        const newCount =
          run.new_records ??
          (run.total_records != null && run.previous_count != null
            ? Math.max(run.total_records - run.previous_count, 0)
            : run.rows ?? 0);
        const totalCount = run.total_records ?? null;

        if (trackedResources.includes(resource)) {
          newCounts[resource] = newCount;
          if (totalCount !== null) {
            totalCounts[resource] = totalCount;
          }
        }
      });

      const aggregateNew = newCounts.users + newCounts.models + newCounts.chats;
      const isFullReload = scope === "all";
      const resourceSet = new Set(runs.map((run) => run.resource));
      const includesMultipleTrackedResources = trackedResources.filter((resource) => resourceSet.has(resource)).length > 1;

      if (isFullReload || includesMultipleTrackedResources) {
        if (aggregateNew > 0) {
          return {
            message: `Loaded users: ${formatNumber(newCounts.users)}, models: ${formatNumber(newCounts.models)}, chats: ${formatNumber(newCounts.chats)}`,
            variant: "success",
          };
        }
        return { message: "Data synchronized. No new records found.", variant: "default" };
      }

      const targetResource = scope ?? (runs[0]?.resource as ReloadResource | undefined);
      if (targetResource) {
        const label = `${targetResource.charAt(0).toUpperCase()}${targetResource.slice(1)}`;
        const newCount =
          targetResource in newCounts
            ? newCounts[targetResource]
            : runs[0]?.new_records ?? runs[0]?.rows ?? 0;
        const totalCount =
          targetResource in totalCounts
            ? totalCounts[targetResource]
            : runs[0]?.total_records ?? null;

        if ((newCount ?? 0) > 0) {
          const totalText = totalCount != null ? ` (total ${formatNumber(totalCount)})` : "";
          return { message: `${label} loaded ${formatNumber(newCount)} new${totalText}`, variant: "success" };
        }
        return {
          message: `${label} synchronized. No new records found.`,
          variant: "default",
        };
      }

      return { message: "Data synchronized.", variant: "default" };
    },
    [],
  );

  const loadAdminStatus = useCallback(async () => {
    try {
      setAdminLoading(true);
      setAdminError(null);
      const status = await fetchDatabaseStatus();
      setAdminStatus(status);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load configuration details.";
      setAdminError(message);
      toast.error(message);
    } finally {
      setAdminLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAdminStatus();
  }, [loadAdminStatus]);

  useEffect(() => {
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
    } catch (error) {
      console.warn("Unable to build locale formatter", error);
    }
  }, []);

  useEffect(() => {
    return () => {
      if (lastReloadTimerRef.current) {
        clearTimeout(lastReloadTimerRef.current);
      }
    };
  }, []);

  const handleReload = useCallback(
    async (resource: ReloadResource) => {
      setAdminError(null);
      setLastReloadRuns([]);
      setAdminLoading(true);

      try {
        const runs = await reloadDatabase(resource, reloadMode);
        setLastReloadRuns(runs);
        if (lastReloadTimerRef.current) {
          clearTimeout(lastReloadTimerRef.current);
        }
        lastReloadTimerRef.current = setTimeout(() => setLastReloadRuns([]), 4000);

        const status = await fetchDatabaseStatus();
        setAdminStatus(status);

        const { message, variant } = summarizeRuns(runs, resource);
        toast({ type: variant, message });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Reload failed";
        setAdminError(message);
        toast.error(message);
      } finally {
        setAdminLoading(false);
      }
    },
    [reloadMode, summarizeRuns],
  );

  const truncateDisabledForUsers = reloadMode === "truncate";

  const lastRunSummary = useMemo(() => {
    if (lastReloadRuns.length === 0) {
      return null;
    }
    return lastReloadRuns
      .map((run) => {
        const newCount = run.new_records ?? run.rows ?? null;
        const totalCount = run.total_records ?? null;
        const details: string[] = [];
        if (newCount !== null) {
          details.push(`+${formatNumber(newCount)}`);
        }
        if (totalCount !== null) {
          details.push(`total ${formatNumber(totalCount)}`);
        }
        const detailText = details.length > 0 ? ` – ${details.join(", ")}` : "";
        return `${run.resource} (${run.status}${detailText})`;
      })
      .join(" • ");
  }, [lastReloadRuns]);

  return (
    <>
      <Header />
      <main className="page-root">
        <div className="dashboard-container space-y-6" style={{ position: "relative" }}>
          <section className="dashboard-header space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h1 className="text-3xl font-semibold text-slate-900">System configuration</h1>
                <p className="text-sm text-slate-600">
                  Monitor data pipelines, trigger reloads, and audit synchronization health.
                </p>
              </div>
              <button
                type="button"
                onClick={loadAdminStatus}
                disabled={adminLoading}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-indigo-400 hover:text-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
              >
                {adminLoading ? "Refreshing..." : "Refresh status"}
              </button>
            </div>
            <AdminNavigation />
          </section>

          {adminError ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{adminError}</div>
          ) : null}

          <section className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="grid gap-6 lg:grid-cols-3">
              <article className="rounded-xl border border-slate-200 p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Database engine</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">
                  {adminStatus
                    ? adminStatus.engine === "postgres"
                      ? "PostgreSQL"
                      : "SQLite"
                    : adminLoading
                    ? "Loading..."
                    : "Unknown"}
                </p>
                <dl className="mt-4 space-y-2 text-sm text-slate-600">
                  <div className="flex justify-between">
                    <dt>Last update</dt>
                    <dd suppressHydrationWarning>
                      {adminStatus?.last_update
                        ? formatDateTime(adminStatus.last_update, headerFormatter ?? undefined)
                        : "Not available"}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>Load duration</dt>
                    <dd>
                      {adminStatus?.last_duration_seconds != null
                        ? `${adminStatus.last_duration_seconds.toFixed(2)}s`
                        : "Not available"}
                    </dd>
                  </div>
                </dl>
              </article>

              <article className="rounded-xl border border-slate-200 p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Row counts</p>
                <ul className="mt-4 space-y-2 text-sm text-slate-700">
                  <li>👥 Users: {formatNumber(adminStatus?.row_counts.users)}</li>
                  <li>💬 Chats: {formatNumber(adminStatus?.row_counts.chats)}</li>
                  <li>🧠 Models: {formatNumber(adminStatus?.row_counts.models)}</li>
                </ul>
              </article>

              <article className="rounded-xl border border-slate-200 p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Reload mode</p>
                <div className="mt-4 space-y-3 text-sm text-slate-700">
                  <label className="flex items-center gap-3">
                    <input
                      type="radio"
                      name="reload-mode"
                      value="upsert"
                      checked={reloadMode === "upsert"}
                      onChange={() => setReloadMode("upsert")}
                      disabled={adminLoading}
                    />
                    Upsert (merge records)
                  </label>
                  <label className="flex items-center gap-3">
                    <input
                      type="radio"
                      name="reload-mode"
                      value="truncate"
                      checked={reloadMode === "truncate"}
                      onChange={() => setReloadMode("truncate")}
                      disabled={adminLoading}
                    />
                    Truncate (full reset)
                  </label>
                  {truncateDisabledForUsers && (
                    <span className="text-xs text-slate-500">
                      Truncate is only supported when using the Reload All action.
                    </span>
                  )}
                </div>
              </article>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                className="filter-button"
                onClick={() => handleReload("all")}
                disabled={adminLoading}
                style={{ backgroundColor: "#2563eb", color: "#fff" }}
              >
                {adminLoading ? "Working..." : `Reload All (${reloadMode})`}
              </button>
              <button
                type="button"
                className="filter-button secondary"
                onClick={() => handleReload("models")}
                disabled={adminLoading}
              >
                Reload Models
              </button>
              <button
                type="button"
                className="filter-button secondary"
                onClick={() => handleReload("users")}
                disabled={adminLoading || truncateDisabledForUsers}
                title={truncateDisabledForUsers ? "Switch to upsert mode to reload users." : undefined}
              >
                Reload Users
              </button>
              <button
                type="button"
                className="filter-button secondary"
                onClick={() => handleReload("chats")}
                disabled={adminLoading}
              >
                Reload Chats
              </button>
              <button
                type="button"
                className="filter-button"
                onClick={loadAdminStatus}
                disabled={adminLoading}
              >
                Refresh Status
              </button>
            </div>

            {adminLoading && (
              <p className="muted-text" style={{ marginTop: "0.75rem" }}>
                Processing admin request...
              </p>
            )}

            {lastRunSummary && (
              <div
                style={{
                  marginTop: "1rem",
                  padding: "0.75rem 1rem",
                  borderRadius: "8px",
                  backgroundColor: "#ecfdf5",
                  border: "1px solid #34d399",
                  color: "#047857",
                }}
              >
                <strong>Latest action:</strong> {lastRunSummary}
              </div>
            )}

            <div className="table-wrapper" style={{ marginTop: "1.5rem" }}>
              {adminStatus && adminStatus.recent_runs.length > 0 ? (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Resource</th>
                      <th scope="col">Mode</th>
                      <th scope="col">Status</th>
                      <th scope="col">Previous Count</th>
                      <th scope="col">New Records</th>
                      <th scope="col">Total Records</th>
                      <th scope="col">Finished</th>
                    </tr>
                  </thead>
                  <tbody>
                    {adminStatus.recent_runs.map((run, index) => (
                      <tr key={`${run.resource}-${run.finished_at ?? index}`}>
                        <td>{run.resource}</td>
                        <td>{run.mode}</td>
                        <td>{run.status}</td>
                        <td>{typeof run.previous_count === "number" ? formatNumber(run.previous_count) : "—"}</td>
                        <td>{typeof run.new_records === "number" ? formatNumber(run.new_records) : "—"}</td>
                        <td>{typeof run.total_records === "number" ? formatNumber(run.total_records) : "—"}</td>
                        <td suppressHydrationWarning>
                          {run.finished_at ? formatDateTime(run.finished_at, headerFormatter ?? undefined) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted-text">No reload activity recorded yet.</p>
              )}
            </div>
          </section>
        </div>
      </main>
    </>
  );
}
