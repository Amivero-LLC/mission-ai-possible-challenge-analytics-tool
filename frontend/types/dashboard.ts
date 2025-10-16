export type SortOption = "completions" | "attempts" | "efficiency";

export interface UserInfo {
  user_id: string;
  user_name: string;
  email?: string;
}

export interface UserChallengeExportRow {
  user_name: string;
  email: string;
  challenge_name: string;
  status: string;
  completed: string;
  num_attempts: number;
  num_messages: number;
  week: string;
  datetime_started: string | null;
  datetime_completed: string | null;
  points_earned: number;
}

export interface Summary {
  total_chats: number;
  mission_attempts: number;
  mission_completions: number;
  success_rate: number;
  unique_users: number;
  unique_missions: number;
  missions_list: string[];
  weeks_list: number[];
  users_list: UserInfo[];
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
  first_attempt?: string | number | null;
  last_attempt?: string | number | null;
  total_points: number;
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

export interface ChallengeResultEntry {
  user_id: string;
  user_name: string;
  status: string; // "Completed", "Attempted", or empty string
  num_attempts: number;
  first_attempt_time?: string | number | null;
  completed_time?: string | number | null;
  num_messages: number;
}

export interface DashboardResponse {
  generated_at: string;
  summary: Summary;
  leaderboard: LeaderboardEntry[];
  mission_breakdown: MissionBreakdownEntry[];
  all_chats: ChatPreview[];
  challenge_results: ChallengeResultEntry[];
  export_data: UserChallengeExportRow[];
}
