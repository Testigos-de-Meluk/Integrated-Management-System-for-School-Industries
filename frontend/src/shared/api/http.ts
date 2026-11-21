/** HTTP client for the IMSI REST API. All calls use relative URLs under /api. */
import { getDevRole } from "@/shared/auth/devRole";

/** Error body returned by every API endpoint: a general message plus messages per field. */
export type ApiErrorBody = {
  detail: string;
  errors: Record<string, string[]>;
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
    const body = this.body as Partial<ApiErrorBody> | null;
    return body?.errors ?? {};
  }
}

function readDetail(body: unknown): string | null {
  if (body && typeof body === "object" && "detail" in body) {
    return String((body as { detail: unknown }).detail);
  }
  return null;
}

type QueryValue = string | number | undefined | null;

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

async function request<T>(
  method: string,
  path: string,
  options: { body?: unknown; query?: Record<string, QueryValue> } = {},
): Promise<T> {
  const response = await fetch(buildUrl(path, options.query), {
    method,
    headers: {
      Accept: "application/json",
      "X-Dev-Role": getDevRole(), // TEMPORARY: replaced by the JWT once login exists.
      ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
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
};

/** Kept for existing callers. */
export const apiGet = <T>(path: string) => api.get<T>(path);

/** Standard envelope of every paginated listing. */
export type Paginated<T> = {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: T[];
};
