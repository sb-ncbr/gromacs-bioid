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
  /** 2026-11-18 (absent from older APIs) */
  queue?: string;
  attempt?: number;
  retry_at?: number | null;
  incomplete?: number;
  superseded_by?: string | null;
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

export interface LimitException {
  label: string;
  per_hour: number;
}

export interface LimitSettings {
  /** 0 = no limit. */
  submit_per_hour: number;
  /** 0 = no cap. */
  queue_cap: number;
  /** IP address or CIDR range -> its own hourly limit. */
  exceptions: Record<string, LimitException>;
  defaults: { submit_per_hour: number; queue_cap: number };
}

export interface LimitsSection extends LimitSettings {
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
  reports?: Section<{ open: number; total: number }>;
  checks?: Section<ChecksSummary>;
  services?: Section<ServicesSummary>;
  /** BLAST services with an NVMe copy (2026-11-19); absent from older APIs. */
  blast_services?: Section<BlastService[]>;
  /** One card per queue (2026-11-18); absent from older APIs. */
  lanes?: Section<LaneCard[]>;
}

// -- queues as cards: workers, retry policy, token (2026-11-18) --------------

export interface RetryPolicy {
  enabled: boolean;
  max_attempts: number;
  delay_minutes: number;
  /** retry runs incomplete for retryable reasons */
  incomplete: boolean;
  /** retry runs whose worker was lost */
  worker_lost: boolean;
}

export interface LaneCard {
  /** "web" | "repository"; null for queues outside BioID's lanes (fleet, bughunt). */
  lane: string | null;
  title: string;
  about: string;
  queue: string;
  deployment: string | null;
  waiting: number | null;
  paused: boolean;
  running: number;
  reserved: number;
  consumers: { name: string; active: WorkerInfo["active"]; reserved: number }[];
  pool: {
    replicas: number | null; ready: number | null; updated: number | null;
    image: string | null; scale: [number, number] | null; error?: string; crashing: number;
  } | null;
  runs: Record<string, number>;
  retry_waiting: number;
  retry_policy: RetryPolicy | null;
  token: { created_at: number; hint: string } | null;
  errors: string[];
}

// -- calls per database / web service (2026-11-18, service_stats.py) --------

export interface ServiceRow {
  /** "db:<resolver>[@sim]" (identify lookups) or "http:<host>" (every HTTP request). */
  service: string;
  /** Pipeline stage, e.g. identify_molecules or verify_results. */
  stage: string;
  calls: number;
  cached: number;
  errors: number;
  error_share: number | null;
  retries: number;
  outcomes: Record<string, number>;
  mean_s: number | null;
  /** Upper edge of the latency bin (approximate). */
  p50_s: number | null;
  p95_s: number | null;
}

export interface ServiceRunning {
  service: string;
  stage: string;
  /** Unix seconds. */
  started: number;
  pod: string;
}

export interface ServicesSummary {
  last_30m: ServiceRow[];
  last_24h: ServiceRow[];
  failing: { service: string; calls: number; errors: number; outcomes: Record<string, number> }[];
  running: ServiceRunning[];
  ncbi_running: number;
  ncbi_alarm_at: number;
}

// -- reports and the nightly known-answers check (2026-11-17) ----------------

export interface IdentificationReport {
  id: string;
  run_id: string;
  segment: string;
  note: string;
  suggestion: string;
  answer: { state: string; database: string; identifier: string; url: string; confidence: number | null; name?: string | null };
  run_name?: string | null;
  created_at: string;
  status: "open" | "resolved" | "dismissed";
  admin_note: string;
}

export interface CheckAnswer {
  state: string;
  database: string;
  identifier: string;
  answered_by: string[];
}

export interface CheckDiff {
  kind: "identity" | "database" | "run";
  segment?: string;
  resolver?: string;
  expected?: string;
  observed: string;
  repeated?: boolean;
}

export interface CheckCase {
  run_id: string;
  label: string;
  expected: Record<string, CheckAnswer>;
  added_at: string;
  accepted_at?: string;
}

export interface CheckState {
  status?: "running" | "green" | "amber" | "red";
  started_at?: number;
  finished_at?: number | null;
  runs?: Record<string, string | null>;
  results?: Record<string, { status: string; check_run?: string; diffs: CheckDiff[] }>;
  last_completed?: { started_at?: number; finished_at?: number; status?: string } | null;
}

export interface ChecksSummary {
  cases: number;
  status?: string | null;
  started_at?: number | null;
  finished_at?: number | null;
}

export interface ChecksDetail {
  cases: CheckCase[];
  check: CheckState;
  crash_loops: { deployment: string; pods: number; of: number; reason: string; last_exit: string | null }[] | { error: string };
  alerts: { at: number; key: string; subject: string; sent: boolean; error?: string }[];
  alert_email: string | null;
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
  const contentType = res.headers.get("content-type") ?? "";
  // The API never answers HTML: an HTML page here is the ingress's error page
  // (served with status 200 while the API is down), not data (2026-11-17).
  if (contentType.includes("text/html")) {
    throw new ApiError(503, JSON.stringify({ detail: "BioID's server is not available right now. Please try again in a few minutes." }), 60);
  }
  return (contentType.includes("application/json") ? await res.json() : await res.text()) as T;
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

  setLimits: (token: string, limits: { submit_per_hour?: number; queue_cap?: number }) =>
    request<LimitSettings>("/settings/limits", token, { method: "PUT", body: JSON.stringify(limits) }),
  setLimitException: (token: string, address: string, label: string, perHour: number) =>
    request<LimitSettings>("/settings/limits/exceptions", token, {
      method: "PUT",
      body: JSON.stringify({ address, label, per_hour: perHour }),
    }),
  reports: (token: string) => request<{ reports: IdentificationReport[]; open: number }>("/reports", token),
  updateReport: (token: string, id: string, change: { status?: string; admin_note?: string }) =>
    request<IdentificationReport>(`/reports/${seg(id)}`, token, { method: "PUT", body: JSON.stringify(change) }),
  checks: (token: string) => request<ChecksDetail>("/checks", token),
  addCase: (token: string, runId: string, label: string) => post<CheckCase>("/checks/cases", token, { run_id: runId, label }),
  removeCase: (token: string, runId: string) =>
    request<{ removed: string }>(`/checks/cases/${seg(runId)}`, token, { method: "DELETE" }),
  acceptCase: (token: string, runId: string) => post<CheckCase>(`/checks/cases/${seg(runId)}/accept`, token),
  runCheck: (token: string) => post<CheckState>("/checks/run", token),
  testAlarm: (token: string) => post<{ sent: boolean; to: string }>("/alerts/test", token),
  setRetryPolicy: (token: string, lane: string, change: Partial<RetryPolicy>) =>
    request<{ lane: string; retry_policy: RetryPolicy }>(`/lanes/${seg(lane)}/retry`, token,
      { method: "PUT", body: JSON.stringify(change) }),
  newQueueToken: (token: string, lane: string) =>
    post<{ lane: string; token: string; header: string }>(`/lanes/${seg(lane)}/token`, token),
  revokeQueueToken: (token: string, lane: string) =>
    request<{ lane: string; revoked: boolean }>(`/lanes/${seg(lane)}/token`, token, { method: "DELETE" }),
  removeLimitException: (token: string, address: string) =>
    request<LimitSettings>(`/settings/limits/exceptions?address=${seg(address)}`, token, { method: "DELETE" }),
};

// -- BLAST services with an NVMe copy (2026-11-19) ----------------------------

export interface BlastService {
  db: string;
  deployment: string;
  url: string;
  /** the release the NFS symlink points to (what workers search) */
  nfs_release: string | null;
  /** staging | ready | error | "no answer" */
  state: string;
  /** the release it serves (null while it has none) */
  release?: string | null;
  /** a snapshot it downloads ahead of the NFS switch */
  prefetch?: string | null;
  error: string;
  blast_version?: string;
  threads?: number;
  counts?: { running: number; waiting: number; searches: number; timeouts: number; failures: number };
  staging?: {
    release?: string; source?: string; done_bytes?: number; total_bytes?: number;
    files_done?: number; files_total?: number; started?: number; finished?: number;
  };
  /** workers send searches here: ready, and the same release as NFS */
  used_by_workers: boolean;
}
