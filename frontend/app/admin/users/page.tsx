'use client';

import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import AdminNavigation from "../../../components/AdminNavigation";
import Header from "../../../components/Header";
import { fetchAdminUsers, syncAdminUsers, updateAdminUser } from "../../../lib/auth";
import type { AuthUser } from "../../../types/auth";

interface ColumnConfig {
  label: string;
  render: (user: AuthUser) => ReactNode;
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        setIsLoading(true);
        const response = await fetchAdminUsers();
        if (active) {
          setUsers(response.users);
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Unable to load users");
        }
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }
    load();
    return () => {
      active = false;
    };
  }, []);

  async function handleUpdate(id: string, updates: Partial<AuthUser>) {
    try {
      setError(null);
      const result = await updateAdminUser(id, {
        is_active: updates.is_active,
        is_approved: updates.is_approved,
        role: updates.role,
      });
      setUsers((prev) => prev.map((user) => (user.id === result.id ? result : user)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update user");
    }
  }

  async function handleSync() {
    try {
      setIsSyncing(true);
      setError(null);
      await syncAdminUsers({ emails: [] });
      const refreshed = await fetchAdminUsers();
      setUsers(refreshed.users);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sync users");
    } finally {
      setIsSyncing(false);
    }
  }

  const columns: ColumnConfig[] = useMemo(
    () => [
      {
        label: "User",
        render: (user) => (
          <div className="space-y-0.5">
            <p
              className={`font-semibold ${
                user.username ? "text-slate-900" : "text-slate-500"
              }`}
            >
              {user.username ?? "Pending profile"}
            </p>
            <p className="text-xs text-slate-500">{user.email}</p>
          </div>
        ),
      },
      {
        label: "Provider",
        render: (user) => (
          <span className="inline-flex items-center rounded-full bg-slate-900/80 px-3 py-0.5 text-xs font-semibold uppercase tracking-wide text-white">
            {user.auth_provider === "o365" ? "Microsoft 365" : "Local"}
          </span>
        ),
      },
      {
        label: "Status",
        render: (user) => (
          <div className="flex flex-col gap-1 text-xs font-semibold">
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 ring-1 ring-inset ${
                user.is_approved
                  ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                  : "bg-amber-50 text-amber-700 ring-amber-200"
              }`}
            >
              {user.is_approved ? "Approved" : "Awaiting approval"}
            </span>
            {user.is_active ? (
              user.is_approved ? (
                user.last_login_at ? (
                  <span className="inline-flex items-center rounded-full bg-sky-50 px-2.5 py-0.5 text-sky-700 ring-1 ring-inset ring-sky-200">
                    Active
                  </span>
                ) : (
                  <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-amber-700 ring-1 ring-inset ring-amber-200">
                    Pending first login
                  </span>
                )
              ) : null
            ) : (
              <span className="inline-flex items-center rounded-full bg-rose-50 px-2.5 py-0.5 text-rose-700 ring-1 ring-inset ring-rose-200">
                Suspended
              </span>
            )}
          </div>
        ),
      },
      {
        label: "Role",
        render: (user) => (
          <span className="inline-flex items-center rounded-full bg-indigo-600/90 px-3 py-0.5 text-xs font-semibold uppercase tracking-wide text-white">
            {user.role}
          </span>
        ),
      },
      {
        label: "Actions",
        render: (user) => (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => handleUpdate(user.id, { is_approved: !user.is_approved })}
              className="rounded-md border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-700 transition hover:border-indigo-400 hover:bg-indigo-50 hover:text-indigo-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
            >
              {user.is_approved ? "Revoke" : "Approve"}
            </button>
            <button
              type="button"
              onClick={() => handleUpdate(user.id, { is_active: !user.is_active })}
              className="rounded-md border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-700 transition hover:border-indigo-400 hover:bg-indigo-50 hover:text-indigo-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
            >
              {user.is_active ? "Suspend" : "Activate"}
            </button>
          </div>
        ),
      },
    ],
    [],
  );

  return (
    <>
      <Header />
      <main className="page-root">
        <div className="dashboard-container space-y-6">
          <section className="dashboard-header space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h1 className="text-3xl font-semibold text-slate-900">User approvals</h1>
                <p className="text-sm text-slate-600">
                  Approve new teammates, manage authentication providers, and keep your workspace secure.
                </p>
              </div>
              <button
                type="button"
                onClick={handleSync}
                disabled={isSyncing}
                className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
              >
                {isSyncing ? "Syncing..." : "Sync Open WebUI"}
              </button>
            </div>
            <AdminNavigation />
          </section>
          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
          ) : null}
          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-b from-white to-slate-50 shadow-sm">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-900 text-left text-xs font-semibold uppercase tracking-wide text-slate-100">
                <tr>
                  {columns.map((column) => (
                    <th key={column.label} className="px-4 py-3">
                      {column.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white text-slate-800">
                {isLoading ? (
                  <tr>
                    <td className="px-4 py-6 text-center text-sm" colSpan={columns.length}>
                      Loading users...
                    </td>
                  </tr>
                ) : users.length === 0 ? (
                  <tr>
                    <td className="px-4 py-6 text-center text-sm text-slate-500" colSpan={columns.length}>
                      No users found. Sync with Open WebUI or invite teammates.
                    </td>
                  </tr>
                ) : (
                  users.map((user) => (
                    <tr key={user.id} className="hover:bg-slate-50">
                      {columns.map((column) => (
                        <td key={column.label} className="px-4 py-3 align-top">
                          {column.render(user)}
                        </td>
                      ))}
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
