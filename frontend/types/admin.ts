export type ReloadMode = "upsert" | "truncate";
export type ReloadResource = "users" | "chats" | "models" | "all";

export interface ReloadRun {
  resource: string;
  mode: ReloadMode | string;
  status: string;
  rows?: number | null;
  message?: string | null;
  finished_at?: string | null;
  previous_count?: number | null;
  new_records?: number | null;
  total_records?: number | null;
  duration_seconds?: number | null;
}

export interface DatabaseStatus {
  engine: string;
  row_counts: Record<string, number>;
  last_update?: string | null;
  last_duration_seconds?: number | null;
  recent_runs: ReloadRun[];
}
