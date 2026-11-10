/**
 * Admin API (src_new/api/admin.py): the /admin operations dashboard.
 *
 * Auth is a signed session token from POST /admin/login, kept in
 * sessionStorage (this tab only) and sent as `Authorization: Bearer`. These
 * routes are not in the published OpenAPI schema, so the types live here.
 */
import { API_BASE, ApiError } from "./client";

const BASE = `${API_BASE}/admin`;
const TOKEN_KEY = "bioid.admin.session";

/** Any overview section may be replaced by this when it failed server side. */
export interface SectionError {
  error: string;
}

export function isSectionError(value: unknown): value is SectionError {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    typeof (value as { error?: unknown }).error === "string" &&
    Object.keys(value).length === 1
  );
}

export interface QueuesSection {
  queues: { name: string; waiting: number }[];
  paused: string[];
  error?: string;
}

export interface WorkerInfo {
  name: string;
  queues: string[];
  /** `started` is a unix time in seconds (Celery's time_start). */
  active: { run_id: string | null; started: number | null }[];
  reserved: number;
}

export interface WorkersSection {
  workers: WorkerInfo[];
  error?: string;
}

export interface PodInfo {
  name: string;
  phase: string | null;
  ready: boolean;
  restarts: number;
  waiting: string | null;
  last_exit: string | null;
  started: string | null;
  node: string | null;
  deleting: boolean;
}

export interface DeploymentInfo {
  name: string;
  label: string;
  replicas: number | null;
  ready: number;
  updated: number;
  image: string;
  /** [min, max] replicas, or null when it cannot be scaled from here. */
  scale: [number, number] | null;
  restartable: boolean;
  pods: PodInfo[];
}

/** One deployment that could not be read (the others still are). */
export interface DeploymentError {
  name: string;
  label: string;
  error: string;
}

export type RetentionPolicy = "default" | "preserve" | "days";

export interface RunRetention {
  policy: RetentionPolicy | string;
  days: number | null;
  expires_at: string | null;
}

export interface AdminRun {
  run_id: string;
  status: string;
  run_name: string | null;
  input_kind: string | null;
  preset: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  updated_at: string | null;
  warning_count: number;
  error: string | null;
  retention: RunRetention;
  has_owner_token: boolean;
  example: boolean;
}

export interface RunsSection {
  total: number;
  by_status: Record<string, number>;
  submitted_24h: number;
  submitted_7d: number;
  active: AdminRun[];
  recent_failures: AdminRun[];
  recent: AdminRun[];
  expiring_soon: AdminRun[];
}

export interface StorageSection {
  runs_bytes: number;
  trash_bytes: number;
  adhoc_bytes: number;
  loose_files: { name: string; bytes: number }[];
  pvcs: { name: string; capacity: string | null }[];
  pvc_error?: string;
}

export interface RetentionSweep {
  enforce: boolean;
  due: number;
  total_runs: number;
  /** Run ids moved to the trash (older records may hold a count). */
  moved: string[] | number;
  /** Run ids purged from the trash. */
  purged: string[] | number;
  /** Why the sweep expired nothing (circuit breaker), else null. */
  aborted: string | null;
  /** Unix seconds. */
  at: number | null;
}

export interface RetentionSection {
  enforce: boolean;
  default_days: number;
  grace_days: number;
  last_sweep: RetentionSweep | null;
  expired: { run_id: string; expired_at: string | null; purge_at: string | null }[];
}

export interface LimitsSection {
  submit_per_hour: number;
  queue_cap: number;
  max_files: number;
}

type Section<T> = T | SectionError;

export interface AdminOverview {
  /** Server time, unix seconds. */
  time: number;
  code_version: string;
  queues: Section<QueuesSection>;
  workers: Section<WorkersSection>;
  deployments: Section<(DeploymentInfo | DeploymentError)[]>;
  runs: Section<RunsSection>;
  storage: Section<StorageSection>;
  retention: Section<RetentionSection>;
  limits: Section<LimitsSection>;
}

// -- traffic ------------------------------------------------------------------

export const TRAFFIC_WINDOWS = ["1h", "24h", "7d", "30d", "90d", "all"] as const;
export type TrafficWindow = (typeof TRAFFIC_WINDOWS)[number];

export interface TrafficCount {
  name: string;
  count: number;
}

/** One bucket of the time series; buckets with no traffic are left out. */
export interface TrafficBucket {
  /** UTC "YYYY-MM-DDTHH" (hourly) or "YYYY-MM-DD" (daily). */
  t: string;
  requests: number;
  pageviews: number;
  visitors: number;
}

export interface TrafficCountry {
  code: string;
  name: string;
  visitors: number;
  pageviews: number;
  requests: number;
}

export interface TrafficPlace {
  /** Rounded to 0.1 degree. */
  lat: number;
  lon: number;
  city: string;
  /** ISO country code. */
  country: string;
  visitors: number;
  pageviews: number;
  requests: number;
}

/** GET /admin/traffic (src_new/api/traffic.py summarize()). */
export interface TrafficStats {
  window: TrafficWindow;
  /** ISO time; for "all" the first recorded UTC day ("YYYY-MM-DD"), or null when nothing is kept. */
  from: string | null;
  to: string;
  bucket: "hour" | "day";
  totals: {
    visitors: number;
    pageviews: number;
    requests: number;
    runs: number;
    errors: number;
    rate_limited: number;
    countries: number;
    p50_ms: number | null;
    p95_ms: number | null;
  };
  runs_by_client: Record<string, number>;
  series: TrafficBucket[];
  countries: TrafficCountry[];
  places: TrafficPlace[];
  pages: TrafficCount[];
  endpoints: TrafficCount[];
  /** HTTP status code -> API requests. */
  status: Record<string, number>;
  clients: Record<string, number>;
  browsers: Record<string, number>;
  referrers: TrafficCount[];
  geoip: { available: boolean; attribution: string };
  raw_days: number;
}

export interface AdminSession {
  token: string;
  /** Unix seconds. */
  expires_at: number;
}

// -- session storage ----------------------------------------------------------

export function loadSession(now = Date.now()): AdminSession | null {
  try {
    const raw = window.sessionStorage.getItem(TOKEN_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AdminSession>;
    if (typeof parsed.token !== "string" || typeof parsed.expires_at !== "number") return null;
    if (parsed.expires_at * 1000 <= now) return null;
    return { token: parsed.token, expires_at: parsed.expires_at };
  } catch {
    return null;
  }
}

export function saveSession(session: AdminSession | null): void {
  try {
    if (session) window.sessionStorage.setItem(TOKEN_KEY, JSON.stringify(session));
    else window.sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage disabled: the session lasts as long as the page
  }
}

// -- requests -------------------------------------------------------------------

async function request<T>(path: string, token: string | null, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body !== undefined) headers.set("Content-Type", "application/json");
  const res = await fetch(`${BASE}${path}`, { ...init, headers, cache: "no-store" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    const retry = Number(res.headers.get("retry-after"));
    throw new ApiError(res.status, body, Number.isFinite(retry) && retry > 0 ? retry : null);
  }
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? await res.json() : await res.text()) as T;
}

const post = <T>(path: string, token: string, body?: unknown) =>
  request<T>(path, token, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

const seg = encodeURIComponent;

export function isUnauthorized(err: unknown): boolean {
  return err instanceof ApiError && err.status === 401;
}

export const adminApi = {
  login: (password: string) =>
    request<AdminSession>("/login", null, { method: "POST", body: JSON.stringify({ password }) }),
  overview: (token: string) => request<AdminOverview>("/overview", token),
  traffic: (token: string, window: TrafficWindow) =>
    request<TrafficStats>(`/traffic?window=${seg(window)}`, token),

  scale: (token: string, name: string, replicas: number) =>
    post<{ name: string; replicas: number }>(`/deployments/${seg(name)}/scale`, token, { replicas }),
  restartDeployment: (token: string, name: string) =>
    post<{ name: string; restarted_at: string }>(`/deployments/${seg(name)}/restart`, token),
  restartPod: (token: string, name: string) =>
    post<{ pod: string; deleted: boolean }>(`/pods/${seg(name)}/delete`, token),
  podLogs: (token: string, name: string, tail: number) =>
    request<string>(`/pods/${seg(name)}/logs?tail=${tail}`, token),

  queue: (token: string, name: string, action: "purge" | "pause" | "resume") =>
    post<{ queue: string; removed?: number; paused?: boolean }>(`/queues/${seg(name)}/${action}`, token),

  cancelRun: (token: string, runId: string) => post<{ run_id: string }>(`/runs/${seg(runId)}/cancel`, token),
  deleteRun: (token: string, runId: string) =>
    post<{ run_id: string; trashed: boolean; grace_days: number }>(`/runs/${seg(runId)}/delete`, token),
  setRetention: (token: string, runId: string, retention: string) =>
    post<{ run_id: string; retention: { policy: string; days?: number } }>(`/runs/${seg(runId)}/retention`, token, {
      retention,
    }),
  restoreRun: (token: string, runId: string) => post<{ run_id: string }>(`/expired/${seg(runId)}/restore`, token),
};
