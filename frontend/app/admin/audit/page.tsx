'use client';

import { useEffect, useMemo, useState } from "react";

import AdminNavigation from "../../../components/AdminNavigation";
import Header from "../../../components/Header";
import { fetchAuditLog } from "../../../lib/auth";
import type { AuditEntry } from "../../../types/auth";

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) {
    return value;
  }
  return date.toLocaleString();
}

export default function AuditLogPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const totalEvents = entries.length;
  const uniqueActions = useMemo(() => {
    return new Set(entries.map((entry) => entry.action)).size;
  }, [entries]);
  const uniqueActors = useMemo(() => {
    return new Set(entries.map((entry) => entry.actor_id ?? "system")).size;
  }, [entries]);

  async function loadAuditLog() {
    try {
      setIsLoading(true);
      setError(null);
      const response = await fetchAuditLog();
      setEntries(response.entries);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load audit log.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadAuditLog();
  }, []);

  return (
    <>
      <Header />
      <main className="page-root">
        <div className="dashboard-container space-y-6">
          <section className="dashboard-header space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h1 className="text-3xl font-semibold text-slate-900">Audit trail</h1>
                <p className="text-sm text-slate-600">
                  Inspect authentication events, approvals, and other security-sensitive actions recorded across the platform.
                </p>
              </div>
              <button
                type="button"
                onClick={loadAuditLog}
                disabled={isLoading}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-indigo-400 hover:text-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
              >
                {isLoading ? "Refreshing..." : "Refresh activity"}
              </button>
            </div>
            <AdminNavigation />
          </section>

          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
          ) : null}

          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <article className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Events captured</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">{isLoading ? "..." : totalEvents}</p>
                <p className="text-xs text-slate-500">All recorded actions within the configured retention window.</p>
              </article>
              <article className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Distinct actions</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">{isLoading ? "..." : uniqueActions}</p>
                <p className="text-xs text-slate-500">Unique action codes triggered by automations and administrators.</p>
              </article>
              <article className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Unique actors</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">{isLoading ? "..." : uniqueActors}</p>
                <p className="text-xs text-slate-500">Number of users or services associated with recorded events.</p>
              </article>
            </div>
          </section>

          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                <tr>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Actor</th>
                  <th className="px-4 py-3">Subject</th>
                  <th className="px-4 py-3">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white text-sm text-slate-700">
                {isLoading ? (
                  <tr>
                    <td className="px-4 py-6 text-center text-sm" colSpan={5}>
                      Loading audit entries...
                    </td>
                  </tr>
                ) : entries.length === 0 ? (
                  <tr>
                    <td className="px-4 py-6 text-center text-sm text-slate-500" colSpan={5}>
                      No audit events recorded for this workspace.
                    </td>
                  </tr>
                ) : (
                  entries.map((entry) => (
                    <tr key={entry.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 text-xs text-slate-500">{formatTimestamp(entry.created_at)}</td>
                      <td className="px-4 py-3 uppercase tracking-wide text-indigo-700">{entry.action}</td>
                      <td className="px-4 py-3 text-xs text-slate-600">{entry.actor_id ?? "—"}</td>
                      <td className="px-4 py-3 text-xs text-slate-600">{entry.user_id ?? "—"}</td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        <pre className="max-h-32 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-700">
                          {entry.details ? JSON.stringify(entry.details, null, 2) : "—"}
                        </pre>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </section>
        </div>
      </main>
    </>
  );
}
