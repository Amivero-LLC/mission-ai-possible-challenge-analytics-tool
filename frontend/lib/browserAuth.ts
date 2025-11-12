const ACCESS_TOKEN_KEY = "maip_access_token";
const TOKEN_EXPIRY_KEY = "maip_token_expires";

function isBrowser(): boolean {
  return typeof window !== "undefined" && typeof window?.localStorage !== "undefined";
}

function removeStoredToken(): void {
  if (!isBrowser()) {
    return;
  }
  try {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    window.localStorage.removeItem(TOKEN_EXPIRY_KEY);
  } catch {
    // Ignore storage exceptions (e.g., quota exceeded or disabled storage)
  }
}

export function getBrowserAccessToken(): string | null {
  if (!isBrowser()) {
    return null;
  }
  try {
    const token = window.localStorage.getItem(ACCESS_TOKEN_KEY);
    const expires = window.localStorage.getItem(TOKEN_EXPIRY_KEY);
    if (!token || !expires) {
      return null;
    }
    const expiresAt = Number(expires);
    if (!Number.isFinite(expiresAt) || Date.now() >= expiresAt) {
      removeStoredToken();
      return null;
    }
    return token;
  } catch {
    return null;
  }
}

export function buildBrowserAuthHeaders(): Record<string, string> {
  const token = getBrowserAccessToken();
  if (!token) {
    return {};
  }
  return {
    Authorization: `Bearer ${token}`,
  };
}
