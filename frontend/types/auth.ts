export type AuthMode = "DEFAULT" | "HYBRID" | "OAUTH";

export type AuthProvider = "local" | "o365";

export type AuthRole = "ADMIN" | "USER";

export interface AuthUser {
  id: string;
  email: string;
  username?: string | null;
  role: AuthRole;
  auth_provider: AuthProvider;
  is_approved: boolean;
  is_active: boolean;
  email_verified: boolean;
  last_login_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "Bearer";
  expires_in: number;
}

export interface OAuthStartResponse {
  authorization_url: string;
  state: string;
}

export interface RegisterStartResponse {
  status: "pending_approval" | "password_setup_required" | "password_reset_required";
  message: string;
}

export interface AdminUserUpdateRequest {
  is_approved?: boolean;
  is_active?: boolean;
  role?: AuthRole;
}

export interface AuditEntry {
  id: number;
  action: string;
  actor_id?: string | null;
  user_id?: string | null;
  details?: Record<string, unknown> | null;
  created_at: string;
}
