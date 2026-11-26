/** HTTP client for the IMSI REST API. All calls use relative URLs under /api. */
import {
  endSession,
  getAccessToken,
  getSessionState,
  startSession,
  waitForSessionCheck,
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
/** Set when the last refresh was refused by the rate limit while the tab was signed in. */
let rateLimitedRefresh: ApiError | null = null;

const REFRESH_LOCK = "imsi-session-refresh";
const CONFLICT_RETRY_DELAY_MS = 500;
/** On page load, how many times to wait out a 429 before giving up (then: login screen). */
const MAX_RATE_LIMIT_WAITS = 3;
const DEFAULT_RETRY_AFTER_SECONDS = 10;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Runs ``task`` while holding a lock shared by every tab of this site (Web Locks API), so two
 * tabs never rotate the shared refresh cookie at the same time. Browsers without it just run it.
 */
async function withCrossTabLock<T>(task: () => Promise<T>): Promise<T> {
  if (typeof navigator === "undefined" || !navigator.locks) return task();
  return (await navigator.locks.request(REFRESH_LOCK, task)) as T;
}

type RefreshResult =
  | { kind: "ok"; session: SessionPayload }
  | { kind: "rate_limited"; error: ApiError; waitSeconds: number }
  | { kind: "failed"; body: unknown };

function retryAfterSeconds(response: Response): number {
  const seconds = Number(response.headers.get("Retry-After"));
  return Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds) : DEFAULT_RETRY_AFTER_SECONDS;
}

/** One refresh call (plus one retry after a ``REFRESH_CONFLICT`` race). */
async function attemptRefresh(): Promise<RefreshResult> {
  const post = () =>
    fetch("/api/auth/refresh/", { method: "POST", headers: { Accept: "application/json" } });
  let response = await post();
  let body: unknown = await response.json().catch(() => null);
  if (response.status === 409 && (body as Partial<ApiErrorBody> | null)?.code === "REFRESH_CONFLICT") {
    await sleep(CONFLICT_RETRY_DELAY_MS);
    response = await post();
    body = await response.json().catch(() => null);
  }
  if (response.ok) return { kind: "ok", session: body as SessionPayload };
  if (response.status === 429) {
    return {
      kind: "rate_limited",
      error: new ApiError(429, body),
      waitSeconds: retryAfterSeconds(response),
    };
  }
  return { kind: "failed", body };
}

/**
 * Asks for a new access token using the httpOnly refresh cookie. Concurrent callers share one
 * request: the refresh token rotates on every use, so two parallel refreshes would look like a
 * stolen token to the backend and close the session. Across tabs, the Web Locks API serializes
 * them; if a race still happens the backend answers 409 ``REFRESH_CONFLICT`` without touching the
 * cookie, and this retries once, by then with the cookie the other tab received.
 *
 * Rate limit (429, ``auth_refresh``): the session is still open on the server, so it is never
 * treated as a logout. On page load the loading screen counts down ``Retry-After`` and retries;
 * inside the app the request that needed the token fails with the server's message.
 */
export function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const wasAuthenticated = getSessionState().status === "authenticated";
      rateLimitedRefresh = null;
      try {
        for (let waits = 0; ; waits++) {
          // The lock is held only during the call, never while waiting out a rate limit.
          const result = await withCrossTabLock(attemptRefresh);
          if (result.kind === "ok") {
            startSession(result.session.access_token, result.session.user);
            return true;
          }
          if (result.kind === "rate_limited") {
            if (wasAuthenticated) {
              rateLimitedRefresh = result.error;
              return false;
            }
            if (waits >= MAX_RATE_LIMIT_WAITS) {
              endSession(result.error.message);
              return false;
            }
            waitForSessionCheck(Date.now() + result.waitSeconds * 1000);
            await sleep(result.waitSeconds * 1000);
            continue;
          }
          // Only explain why when the user was inside the app (not on a plain page load).
          endSession(wasAuthenticated ? readDetail(result.body) : null);
          return false;
        }
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

/**
 * After a 401: renews the token. ``true`` = retry the request. If the renewal was rate-limited,
 * throws that error so the screen shows "Demasiados intentos…" instead of a generic failure.
 */
async function renewAfter401(): Promise<boolean> {
  if (await refreshSession()) return true;
  if (rateLimitedRefresh) throw rateLimitedRefresh;
  return false;
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
  if (response.status === 401 && !options.anonymous && (await renewAfter401())) {
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
  if (response.status === 401 && (await renewAfter401())) {
    response = await send("GET", path, {});
  }
  await saveResponse(response, fallbackName);
}

/**
 * POST that returns a file. Used when the secret that authorizes the download (e.g. a quotation
 * access key) must not travel in the URL, where proxy and server logs would keep it.
 */
export async function postAnonymousBlob(
  path: string,
  body: unknown,
  fallbackName: string,
): Promise<void> {
  await saveResponse(await send("POST", path, { body, anonymous: true }), fallbackName);
}

async function saveResponse(response: Response, fallbackName: string): Promise<void> {
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
