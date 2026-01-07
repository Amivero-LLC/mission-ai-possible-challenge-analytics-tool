'use client';

import { useEffect, useMemo, useState } from "react";

import AdminNavigation from "../../../components/AdminNavigation";
import Header from "../../../components/Header";
import { deleteAdminModel, fetchAdminModels, syncAdminModels, updateAdminModel } from "../../../lib/auth";
import { toast } from "../../../lib/toast";
import type { AdminModel, AdminModelUpdateRequest } from "../../../types/adminModels";

type ModelDraft = {
  name?: string;
  maip_week?: string;
  maip_points?: string;
  maip_difficulty?: string;
  is_challenge?: boolean;
};

type SortKey = "name" | "id" | "week" | "points" | "difficulty" | "updated" | "challenge";
type SortDirection = "asc" | "desc";

function parseWeek(value?: string | null) {
  if (!value) {
    return null;
  }
  const match = value.match(/(\d+)/);
  if (!match) {
    return null;
  }
  const parsed = Number(match[1]);
  return Number.isNaN(parsed) ? null : parsed;
}

function formatTimestamp(value?: string | null) {
  if (!value) {
    return "N/A";
  }
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) {
    return value;
  }
  return date.toLocaleString();
}

function buildPayload(model: AdminModel, draft: ModelDraft): AdminModelUpdateRequest | null {
  const updates: AdminModelUpdateRequest = {};

  if (draft.name !== undefined) {
    const trimmed = draft.name.trim();
    updates.name = trimmed ? trimmed : null;
  }
  if (draft.maip_week !== undefined) {
    const trimmed = draft.maip_week.trim();
    updates.maip_week = trimmed ? trimmed : null;
  }
  if (draft.maip_difficulty !== undefined) {
    const trimmed = draft.maip_difficulty.trim();
    updates.maip_difficulty = trimmed ? trimmed : null;
  }
  if (draft.maip_points !== undefined) {
    const trimmed = draft.maip_points.trim();
    if (!trimmed) {
      updates.maip_points = null;
    } else {
      const parsed = Number(trimmed);
      updates.maip_points = Number.isNaN(parsed) ? null : parsed;
    }
  }
  if (draft.is_challenge !== undefined) {
    updates.is_challenge = draft.is_challenge;
  }

  const hasChanges =
    ("name" in updates && updates.name !== (model.name ?? null)) ||
    ("maip_week" in updates && updates.maip_week !== (model.maip_week ?? null)) ||
    ("maip_difficulty" in updates && updates.maip_difficulty !== (model.maip_difficulty ?? null)) ||
    ("maip_points" in updates && updates.maip_points !== (model.maip_points ?? null)) ||
    ("is_challenge" in updates && updates.is_challenge !== model.is_challenge);

  return hasChanges ? updates : null;
}

export default function AdminModelsPage() {
  const [models, setModels] = useState<AdminModel[]>([]);
  const [drafts, setDrafts] = useState<Record<string, ModelDraft>>({});
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        setIsLoading(true);
        const response = await fetchAdminModels();
        if (active) {
          setModels(response.models);
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Unable to load models");
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

  const filteredModels = useMemo(() => {
    const term = search.trim().toLowerCase();
    const results = term
      ? models.filter((model) => {
        const name = model.name ?? "";
        return (
          model.id.toLowerCase().includes(term) ||
          name.toLowerCase().includes(term) ||
          (model.maip_week ?? "").toLowerCase().includes(term)
        );
      })
      : models;

    const sorted = [...results].sort((a, b) => {
      const dir = sortDirection === "asc" ? 1 : -1;
      const aName = a.name ?? "";
      const bName = b.name ?? "";
      const aWeek = parseWeek(a.maip_week);
      const bWeek = parseWeek(b.maip_week);
      const aDifficulty = a.maip_difficulty ?? "";
      const bDifficulty = b.maip_difficulty ?? "";
      const aPoints = typeof a.maip_points === "number" ? a.maip_points : Number(a.maip_points ?? -1);
      const bPoints = typeof b.maip_points === "number" ? b.maip_points : Number(b.maip_points ?? -1);
      const aUpdated = a.updated_at ?? "";
      const bUpdated = b.updated_at ?? "";

      switch (sortKey) {
        case "name":
          return aName.localeCompare(bName) * dir;
        case "id":
          return a.id.localeCompare(b.id) * dir;
        case "week":
          if (aWeek === null && bWeek === null) {
            return 0;
          }
          if (aWeek === null) {
            return 1 * dir;
          }
          if (bWeek === null) {
            return -1 * dir;
          }
          return (aWeek - bWeek) * dir;
        case "points":
          return (aPoints - bPoints) * dir;
        case "difficulty":
          return aDifficulty.localeCompare(bDifficulty) * dir;
        case "updated":
          return aUpdated.localeCompare(bUpdated) * dir;
        case "challenge":
          return (Number(a.is_challenge) - Number(b.is_challenge)) * dir;
        default:
          return 0;
      }
    });

    return sorted;
  }, [models, search, sortDirection, sortKey]);

  function updateDraft(modelId: string, field: keyof ModelDraft, value: string | boolean) {
    setDrafts((prev) => ({
      ...prev,
      [modelId]: {
        ...prev[modelId],
        [field]: value,
      },
    }));
  }

  function clearDraft(modelId: string) {
    setDrafts((prev) => {
      const next = { ...prev };
      delete next[modelId];
      return next;
    });
  }

  async function handleSync() {
    try {
      setIsSyncing(true);
      setError(null);
      const result = await syncAdminModels();
      const refreshed = await fetchAdminModels();
      setModels(refreshed.models);
      setDrafts({});
      toast.success(result.message ?? "Models synchronized.");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to sync models";
      setError(message);
      toast.error(message);
    } finally {
      setIsSyncing(false);
    }
  }

  async function handleSave(model: AdminModel) {
    const draft = drafts[model.id];
    if (!draft) {
      return;
    }
    const payload = buildPayload(model, draft);
    if (!payload) {
      clearDraft(model.id);
      return;
    }

    try {
      setSavingId(model.id);
      setError(null);
      const updated = await updateAdminModel(model.id, payload);
      setModels((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      clearDraft(model.id);
      toast.success("Model updated.");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to update model";
      setError(message);
      toast.error(message);
    } finally {
      setSavingId((prev) => (prev === model.id ? null : prev));
    }
  }

  async function handleDelete(model: AdminModel) {
    const label = model.name ? `${model.name} (${model.id})` : model.id;
    const confirmed = window.confirm(
      `Delete model "${label}"? This cannot be undone and may remove it from mission tracking.`,
    );
    if (!confirmed) {
      return;
    }

    try {
      setSavingId(model.id);
      setError(null);
      await deleteAdminModel(model.id);
      setModels((prev) => prev.filter((item) => item.id !== model.id));
      clearDraft(model.id);
      toast.success("Model deleted.");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to delete model";
      setError(message);
      toast.error(message);
    } finally {
      setSavingId((prev) => (prev === model.id ? null : prev));
    }
  }

  function handleSort(nextKey: SortKey) {
    setSortKey((current) => {
      if (current === nextKey) {
        return current;
      }
      return nextKey;
    });
    setSortDirection((currentDirection) => {
      if (sortKey === nextKey) {
        return currentDirection === "asc" ? "desc" : "asc";
      }
      return "asc";
    });
  }

  function sortLabel(key: SortKey) {
    if (key !== sortKey) {
      return "";
    }
    return sortDirection === "asc" ? "↑" : "↓";
  }

  return (
    <>
      <Header />
      <main className="page-root">
        <div className="dashboard-container space-y-6">
          <section className="dashboard-header space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h1 className="text-3xl font-semibold text-slate-900">Model admin</h1>
                <p className="text-sm text-slate-600">
                  Sync models from Open WebUI and fill in the MAIP metadata used by the mission dashboard.
                </p>
              </div>
              <button
                type="button"
                onClick={handleSync}
                disabled={isSyncing}
                className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
              >
                {isSyncing ? "Syncing..." : "Sync Models"}
              </button>
            </div>
            <AdminNavigation />
          </section>

          <section className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <div className="flex-1">
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Search</label>
              <input
                type="text"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Filter by id, name, or week"
                className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-600">
              {filteredModels.length} model{filteredModels.length === 1 ? "" : "s"}
            </div>
          </section>

          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
          ) : null}

          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-b from-white to-slate-50 shadow-sm">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-900 text-left text-xs font-semibold uppercase tracking-wide text-slate-100">
                <tr>
                  <th className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => handleSort("name")}
                      className="inline-flex items-center gap-2"
                    >
                      Model <span className="text-slate-300">{sortLabel("name")}</span>
                    </button>
                  </th>
                  <th className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => handleSort("challenge")}
                      className="inline-flex items-center gap-2"
                    >
                      Challenge <span className="text-slate-300">{sortLabel("challenge")}</span>
                    </button>
                  </th>
                  <th className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => handleSort("week")}
                      className="inline-flex items-center gap-2"
                    >
                      Week <span className="text-slate-300">{sortLabel("week")}</span>
                    </button>
                  </th>
                  <th className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => handleSort("points")}
                      className="inline-flex items-center gap-2"
                    >
                      Points <span className="text-slate-300">{sortLabel("points")}</span>
                    </button>
                  </th>
                  <th className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => handleSort("difficulty")}
                      className="inline-flex items-center gap-2"
                    >
                      Difficulty <span className="text-slate-300">{sortLabel("difficulty")}</span>
                    </button>
                  </th>
                  <th className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => handleSort("updated")}
                      className="inline-flex items-center gap-2"
                    >
                      Updated <span className="text-slate-300">{sortLabel("updated")}</span>
                    </button>
                  </th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white text-slate-800">
                {isLoading ? (
                  <tr>
                    <td className="px-4 py-6 text-center text-sm" colSpan={7}>
                      Loading models...
                    </td>
                  </tr>
                ) : filteredModels.length === 0 ? (
                  <tr>
                    <td className="px-4 py-6 text-center text-sm text-slate-500" colSpan={7}>
                      No models found. Try syncing from Open WebUI.
                    </td>
                  </tr>
                ) : (
                  filteredModels.map((model) => {
                    const draft = drafts[model.id] ?? {};
                    const payload = buildPayload(model, draft);
                    const hasChanges = Boolean(payload);
                    return (
                      <tr key={model.id} className="hover:bg-slate-50">
                        <td className="px-4 py-3 align-top">
                          <div className="space-y-2">
                            <input
                              type="text"
                              value={draft.name ?? model.name ?? ""}
                              onChange={(event) => updateDraft(model.id, "name", event.target.value)}
                              className="w-full rounded-md border border-slate-200 px-2 py-1 text-sm text-slate-800 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                            />
                            <p className="text-xs text-slate-500">{model.id}</p>
                          </div>
                        </td>
                        <td className="px-4 py-3 align-top">
                          <label className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600">
                            <input
                              type="checkbox"
                              checked={draft.is_challenge ?? model.is_challenge}
                              onChange={(event) => updateDraft(model.id, "is_challenge", event.target.checked)}
                              className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                            />
                            {draft.is_challenge ?? model.is_challenge ? "Enabled" : "Disabled"}
                          </label>
                        </td>
                        <td className="px-4 py-3 align-top">
                          <input
                            type="number"
                            value={draft.maip_week ?? (model.maip_week ?? "").toString()}
                            onChange={(event) => updateDraft(model.id, "maip_week", event.target.value)}
                            placeholder="1"
                            min={0}
                            className="w-20 rounded-md border border-slate-200 px-2 py-1 text-sm text-slate-800 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                          />
                        </td>
                        <td className="px-4 py-3 align-top">
                          <input
                            type="number"
                            value={draft.maip_points ?? (model.maip_points ?? "").toString()}
                            onChange={(event) => updateDraft(model.id, "maip_points", event.target.value)}
                            placeholder="0"
                            className="w-20 rounded-md border border-slate-200 px-2 py-1 text-sm text-slate-800 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                          />
                        </td>
                        <td className="px-4 py-3 align-top">
                          <input
                            type="text"
                            value={draft.maip_difficulty ?? model.maip_difficulty ?? ""}
                            onChange={(event) => updateDraft(model.id, "maip_difficulty", event.target.value)}
                            placeholder="Medium"
                            className="w-28 rounded-md border border-slate-200 px-2 py-1 text-sm text-slate-800 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                          />
                        </td>
                        <td className="px-4 py-3 align-top text-xs text-slate-500">
                          {formatTimestamp(model.updated_at)}
                        </td>
                        <td className="px-4 py-3 align-top">
                          <div className="flex flex-col gap-2">
                            <button
                              type="button"
                              onClick={() => handleSave(model)}
                              disabled={!hasChanges || savingId === model.id}
                              className="rounded-md border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-700 transition hover:border-indigo-400 hover:bg-indigo-50 hover:text-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {savingId === model.id ? "Saving..." : "Save"}
                            </button>
                            <button
                              type="button"
                              onClick={() => clearDraft(model.id)}
                              disabled={!hasChanges || savingId === model.id}
                              className="rounded-md border border-slate-200 px-3 py-1 text-xs text-slate-500 transition hover:border-slate-300 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              Reset
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDelete(model)}
                              disabled={savingId === model.id}
                              className="rounded-md border border-rose-200 bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700 transition hover:border-rose-300 hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </section>
        </div>
      </main>
    </>
  );
}
