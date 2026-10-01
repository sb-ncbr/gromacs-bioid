/**
 * Typed API client for the BioID pipeline API.
 *
 * Base path migration: the API is being exposed under `/api/v1` (additive);
 * legacy root paths stay live during transition. Endpoints not yet aliased
 * keep working via LEGACY absolute paths below.
 */

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  public readonly status: number;
  public readonly body: string;

  constructor(status: number, body: string) {
    super(`API request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export type QueryParams = Record<string, string | number | boolean | undefined>;

function buildUrl(path: string, params?: QueryParams): string {
  if (!params) return path;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `${path}?${qs}` : path;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body);
  }
  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await res.json()) as T;
  }
  return (await res.text()) as T;
}

export const api = {
  get: <T>(path: string, params?: QueryParams): Promise<T> =>
    request<T>(buildUrl(path, params)),
  postJson: <T>(path: string, body: unknown): Promise<T> =>
    request<T>(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  postForm: <T>(path: string, form: FormData): Promise<T> =>
    request<T>(path, { method: "POST", body: form }),
  delete: <T>(path: string): Promise<T> => request<T>(path, { method: "DELETE" }),
};

/**
 * Endpoint builders. `/api/v1` alias lands in API wave A1 (src_new/api).
 * Until deployed, the SPA is served behind nginx which proxies `/api/*`.
 */
export const endpoints = {
  health: `${API_BASE}/health`,
  healthLegacy: "/health",
  runs: `${API_BASE}/runs`,
  run: (runId: string) => `${API_BASE}/runs/${runId}`,
  runStatus: (runId: string) => `${API_BASE}/runs/${runId}/status`,
  runMolecules: (runId: string) => `${API_BASE}/runs/${runId}/molecules`,
  runMoleculeInfo: (runId: string, segment: string) =>
    `${API_BASE}/runs/${runId}/molecules/${encodeURIComponent(segment)}/info`,
  runLoading: (runId: string) => `${API_BASE}/runs/${runId}/loading`,
  runSignatures: (runId: string) => `${API_BASE}/runs/${runId}/signatures`,
  runIdentifiers: (runId: string) => `${API_BASE}/runs/${runId}/identifiers`,
  runVerification: (runId: string) => `${API_BASE}/runs/${runId}/verification`,
  runFiles: (runId: string) => `${API_BASE}/runs/${runId}/files`,
  runRender: (runId: string) => `${API_BASE}/runs/${runId}/render`,
  runLogs: (runId: string) => `${API_BASE}/runs/${runId}/logs`,
  runRerun: (runId: string) => `${API_BASE}/runs/${runId}/rerun`,
  runQueue: (runId: string) => `${API_BASE}/runs/${runId}/queue`,
  configDefault: `${API_BASE}/runs/config/default`,
  /** Static run-file mount (served by API container, stays on legacy path). */
  runFileUrl: (runId: string, file: string) =>
    `/files/${encodeURIComponent(runId)}/${file.split("/").map(encodeURIComponent).join("/")}`,
} as const;
