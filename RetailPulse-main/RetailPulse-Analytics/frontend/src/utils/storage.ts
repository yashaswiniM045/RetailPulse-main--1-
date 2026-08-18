import { AuthTokens } from "../types/auth";

const TOKEN_KEY = "retailpulse_tokens";

export function saveTokens(tokens: AuthTokens) {
  localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
}

export function loadTokens(): AuthTokens | null {
  const rawValue = localStorage.getItem(TOKEN_KEY);
  if (!rawValue) {
    return null;
  }

  try {
    return JSON.parse(rawValue) as AuthTokens;
  } catch {
    localStorage.removeItem(TOKEN_KEY);
    return null;
  }
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
}
