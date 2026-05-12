import type {
  AuthTokenResponse,
  MeResponse,
  PortalSessionResponse,
} from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

const ACCESS_TOKEN_KEY = "oneloyal.access_token";
const REFRESH_TOKEN_KEY = "oneloyal.refresh_token";
const PORTAL_TOKEN_KEY = "one_loyal_portal_token";

function getPortalAccessPath(): string {
  const path = window.location.pathname;
  const companyMatch = path.match(/^\/([^/]+)\/user(?:\/.*)?$/);
  if (companyMatch?.[1]) {
    return `/${companyMatch[1]}/user/access`;
  }
  return "/portal/access";
}

export class ApiError extends Error {
  status: number;
  details: unknown;

  constructor(message: string, status: number, details: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

export function getStoredAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getStoredRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function storeTokens(tokens: AuthTokenResponse): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function getStoredPortalToken(): string | null {
  return localStorage.getItem(PORTAL_TOKEN_KEY);
}

export function storePortalToken(token: string): void {
  localStorage.setItem(PORTAL_TOKEN_KEY, token);
}

export function clearPortalToken(): void {
  localStorage.removeItem(PORTAL_TOKEN_KEY);
}

function authHeaders(): HeadersInit {
  const token = getStoredAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

type RequestOptions = RequestInit & {
  skipAuth?: boolean;
};

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  const isFormData = options.body instanceof FormData;
  if (!isFormData && options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!options.skipAuth) {
    Object.entries(authHeaders()).forEach(([key, value]) => {
      headers.set(key, String(value));
    });
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;

  if (!response.ok) {
    if (response.status === 401) {
      clearTokens();
    }
    const message =
      payload?.error?.message ?? payload?.detail ?? "Request failed.";
    throw new ApiError(message, response.status, payload?.error?.details ?? payload);
  }

  return payload as T;
}

export async function portalApiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!options.skipAuth) {
    const token = getStoredPortalToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;

  if (!response.ok) {
    if (response.status === 401) {
      clearPortalToken();
      if (
        window.location.pathname.startsWith("/portal") ||
        /\/[^/]+\/user(?:\/|$)/.test(window.location.pathname)
      ) {
        window.history.replaceState(null, "", getPortalAccessPath());
        window.dispatchEvent(new PopStateEvent("popstate"));
      }
    }
    const message =
      payload?.error?.message ?? payload?.detail ?? "Request failed.";
    throw new ApiError(message, response.status, payload?.error?.details ?? payload);
  }

  return payload as T;
}

export async function createPortalSession(
  token: string,
): Promise<PortalSessionResponse> {
  const response = await portalApiRequest<PortalSessionResponse>("/portal/session", {
    method: "POST",
    body: JSON.stringify({ token }),
    skipAuth: true,
  });
  storePortalToken(response.portal_access_token);
  return response;
}

export async function login(email: string, password: string) {
  const response = await apiRequest<AuthTokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
    skipAuth: true,
  });
  storeTokens(response);
  return response;
}

export async function logout(): Promise<void> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) {
    clearTokens();
    return;
  }
  try {
    await apiRequest("/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
      skipAuth: true,
    });
  } finally {
    clearTokens();
  }
}

export async function me(): Promise<MeResponse> {
  return apiRequest<MeResponse>("/auth/me");
}

export function query(params: Record<string, string | number | null | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  });
  const value = search.toString();
  return value ? `?${value}` : "";
}
