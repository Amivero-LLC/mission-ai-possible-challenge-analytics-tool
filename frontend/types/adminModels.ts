export interface AdminModel {
  id: string;
  name?: string | null;
  maip_week?: string | null;
  maip_points?: number | null;
  maip_difficulty?: string | null;
  is_challenge: boolean;
  updated_at?: string | null;
}

export interface AdminModelListResponse {
  models: AdminModel[];
}

export interface AdminModelUpdateRequest {
  name?: string | null;
  maip_week?: string | null;
  maip_points?: number | null;
  maip_difficulty?: string | null;
  is_challenge?: boolean;
}

export interface AdminModelSyncResponse {
  status: string;
  rows: number;
  message?: string | null;
}

export interface AdminModelDeleteResponse {
  status: string;
  message?: string | null;
}
