export interface CampaignUserInfo {
  firstName?: string | null;
  lastName?: string | null;
  email: string;
}

export interface CampaignRow {
  user: CampaignUserInfo;
  pointsByWeek: Record<number, number>;
  totalPoints: number;
  currentRank: number;
}

export interface CampaignSummaryResponse {
  weeks_present: number[];
  rows: CampaignRow[];
  last_upload_at?: string | null;
}

export interface SubmissionReloadSummary {
  rows_inserted: number;
  users_created: number;
  users_updated: number;
  missions_linked: number;
}
