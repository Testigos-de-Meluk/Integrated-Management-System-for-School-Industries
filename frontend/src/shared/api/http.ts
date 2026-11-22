/** HTTP client for the IMSI REST API. All calls use relative URLs under /api. */
import {
  endSession,
  getAccessToken,
  getSessionState,
  startSession,
  type CurrentUser,
} from "@/shared/auth/session";

/** Error body returned by every API endpoint. */
export type ApiErrorBody = {
  detail: string;
  errors: Record<string, string[]>;
  code?: string;
};

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown) {
    super(readDetail(body) ?? `La solicitud falló (código ${status}).`);
    this.status = status;
    this.body = body;
  }

  /** Field errors, e.g. `{ code: ["El código ... ya se encuentra registrado"] }`. */
  get fieldErrors(): Record<string, string[]> {
    return (this.body as Partial<ApiErrorBody> | null)?.errors ?? {};
  }

  /** Machine-readable code, e.g. "SESSION_EXPIRED", "ACCOUNT_LOCKED". */
  get code(): string | undefined {
    return (this.body as Partial<ApiErrorBody> | null)?.code;
  }
}

function readDetail(body: unknown): string | null {
  if (body && typeof body === "object" && "detail" in body) {
    return String((body as { detail: unknown }).detail);
  }
  return null;
}

type QueryValue = string | number | boolean | undefined | null;

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const params = new URLSearchParams();
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  });
  const search = params.toString();
  return `/api${path}${search ? `?${search}` : ""}`;
}

// --- Session renewal ---------------------------------------------------------------------------

export type SessionPayload = {
  access_token: string;
  access_expires_at: string;
  user: CurrentUser;
};

let refreshInFlight: Promise<boolean> | null = null;

/**
 * Asks for a new access token using the httpOnly refresh cookie. Concurrent callers share one
 * request: the refresh token rotates on every use, so two parallel refreshes would look like a
 * stolen token to the backend and close the session.
 */
export function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const wasAuthenticated = getSessionState().status === "authenticated";
      try {
        const response = await fetch("/api/auth/refresh/", {
          method: "POST",
          headers: { Accept: "application/json" },
        });
        const body: unknown = await response.json().catch(() => null);
        if (response.ok) {
          const session = body as SessionPayload;
          startSession(session.access_token, session.user);
          return true;
        }
        // Only explain why when the user was inside the app (not on a plain page load).
        endSession(wasAuthenticated ? readDetail(body) : null);
        return false;
      } catch {
        endSession(wasAuthenticated ? "No fue posible conectar con el servidor." : null);
        return false;
      }
    })().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

// --- Requests ----------------------------------------------------------------------------------

type RequestOptions = {
  body?: unknown;
  query?: Record<string, QueryValue>;
  /** Login endpoints: no token, and a 401 must not trigger a session refresh. */
  anonymous?: boolean;
};

async function send(method: string, path: string, options: RequestOptions): Promise<Response> {
  const token = options.anonymous ? null : getAccessToken();
  return fetch(buildUrl(path, options.query), {
    method,
    headers: {
      Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
}

async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(method, path, options);

  // The access token lasts 5 minutes: on 401, renew it once and retry. If the session itself
  // ended (inactivity, login elsewhere, deactivated account) the refresh fails and the app goes
  // back to the login screen with the reason.
  if (response.status === 401 && !options.anonymous && (await refreshSession())) {
    response = await send(method, path, options);
  }

  if (response.status === 204) return undefined as T;
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(response.status, body);
  }
  return body as T;
}

export const api = {
  get: <T>(path: string, query?: Record<string, QueryValue>) => request<T>("GET", path, { query }),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, { body }),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, { body }),
  delete: <T>(path: string) => request<T>("DELETE", path),
  /** For the login steps, before having an access token. */
  postAnonymous: <T>(path: string, body: unknown) =>
    request<T>("POST", path, { body, anonymous: true }),
};

export const apiGet = <T>(path: string) => api.get<T>(path);

/**
 * Downloads a protected file (e.g. a PDF): a plain link cannot send the Bearer token, so the file
 * is fetched with it and saved from memory.
 */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  let response = await send("GET", path, {});
  if (response.status === 401 && (await refreshSession())) {
    response = await send("GET", path, {});
  }
  if (!response.ok) {
    throw new ApiError(response.status, await response.json().catch(() => null));
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Standard envelope of every paginated listing. */
export type Paginated<T> = {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: T[];
};
