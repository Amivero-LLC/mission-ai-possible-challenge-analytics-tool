export type SortOption = "completions" | "attempts" | "efficiency";

export interface Summary {
  total_chats: number;
  mission_attempts: number;
  mission_completions: number;
  success_rate: number;
  unique_users: number;
  unique_missions: number;
  missions_list: string[];
  participation_rate: number;
}

export interface LeaderboardEntry {
  user_id: string;
  user_name: string;
  attempts: number;
  completions: number;
  efficiency: number;
  total_messages: number;
  unique_missions_attempted: number;
  unique_missions_completed: number;
}

export interface MissionBreakdownEntry {
  mission: string;
  attempts: number;
  completions: number;
  success_rate: number;
  unique_users: number;
}

export interface ChatMessage {
  role?: string | null;
  content?: string | null;
}

export interface ChatPreview {
  num: number;
  title: string;
  user_id: string;
  user_name: string;
  created_at?: string | number | null;
  model: string;
  message_count: number;
  is_mission: boolean;
  completed: boolean;
  messages: ChatMessage[];
}

export interface ModelStatsEntry {
  model: string;
  total: number;
  mission: number;
  completed: number;
  mission_percentage: number;
}

export interface DashboardResponse {
  generated_at: string;
  summary: Summary;
  leaderboard: LeaderboardEntry[];
  mission_breakdown: MissionBreakdownEntry[];
  all_chats: ChatPreview[];
  model_stats: ModelStatsEntry[];
}
