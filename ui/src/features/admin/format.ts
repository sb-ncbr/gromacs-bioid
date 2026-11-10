/** Pure formatting helpers for the admin dashboard (tested in format.test.ts). */
import type { AdminOverview, AdminRun, DeploymentError, DeploymentInfo, RunRetention } from "../../lib/api/admin";
import { isSectionError } from "../../lib/api/admin";

const UNITS = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"];

/** 1536 -> "1.5 KiB"; one decimal below 10 units, none above. */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || !Number.isFinite(bytes) || bytes < 0) return "—";
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  if (unit === 0) return `${Math.round(value)} B`;
  const text = value < 10 ? value.toFixed(1) : String(Math.round(value));
  return `${text.replace(/\.0$/, "")} ${UNITS[unit]}`;
}

/** Milliseconds from an ISO string or unix seconds; null when unparseable. */
export function toMs(value: string | number | null | undefined): number | null {
  if (value == null || value === "") return null;
  if (typeof value === "number") return Number.isFinite(value) ? value * 1000 : null;
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? null : ms;
}

/** 45 -> "45s", 720 -> "12m", 3900 -> "1h 05m", 183600 -> "2d 3h". */
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ${String(m % 60).padStart(2, "0")}m`;
  const d = Math.floor(h / 24);
  return `${d}d ${h % 24}h`;
}

/** "just now", "12s ago", "5m ago", "3h ago", "2d ago"; future: "in 5m". */
export function relativeTime(thenMs: number | null, nowMs: number): string {
  if (thenMs == null) return "—";
  const diff = Math.round((nowMs - thenMs) / 1000);
  const abs = Math.abs(diff);
  if (abs < 5) return "just now";
  let text: string;
  if (abs < 60) text = `${abs}s`;
  else if (abs < 3600) text = `${Math.floor(abs / 60)}m`;
  else if (abs < 86400) text = `${Math.floor(abs / 3600)}h`;
  else text = `${Math.floor(abs / 86400)}d`;
  return diff >= 0 ? `${text} ago` : `in ${text}`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "10 Dec", or "10 Dec 2027" outside the current year (local time). */
export function shortDate(ms: number | null, nowMs: number): string {
  if (ms == null) return "—";
  const d = new Date(ms);
  const base = `${d.getDate()} ${MONTHS[d.getMonth()]}`;
  return d.getFullYear() === new Date(nowMs).getFullYear() ? base : `${base} ${d.getFullYear()}`;
}

/** "10 Dec 14:05" (local time). */
export function dateTime(ms: number | null, nowMs: number): string {
  if (ms == null) return "—";
  const d = new Date(ms);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${shortDate(ms, nowMs)} ${hh}:${mm}`;
}

/**
 * Retention as one line: "kept indefinitely", "30 days (default) · expires 10 Dec",
 * "90 days · expired 2 Nov", "30 days after it finishes".
 */
export function retentionSummary(r: RunRetention | null | undefined, nowMs: number): string {
  if (!r) return "—";
  if (r.policy === "preserve") return "kept indefinitely";
  const days = r.days != null ? `${r.days} day${r.days === 1 ? "" : "s"}` : "default period";
  const label = r.policy === "default" ? `${days} (default)` : days;
  const exp = toMs(r.expires_at);
  if (exp == null) return `${label} after it finishes`;
  return `${label} · ${exp <= nowMs ? "expired" : "expires"} ${shortDate(exp, nowMs)}`;
}

/** Runs still in flight (the backend refuses to delete these). */
export const ACTIVE_STATUSES = new Set(["queued", "running", "pending", "created"]);

export type Tone = "ok" | "warn" | "error" | "info" | "muted";

export function statusTone(status: string): Tone {
  if (status === "success") return "ok";
  if (status === "failed" || status === "error" || status === "timeout") return "error";
  if (status === "cancelled") return "muted";
  if (status === "running") return "info";
  if (ACTIVE_STATUSES.has(status)) return "warn";
  return "muted";
}

export function isDeploymentError(d: DeploymentInfo | DeploymentError): d is DeploymentError {
  return "error" in d;
}

export interface Health {
  waiting: number | null;
  activeRuns: number | null;
  /** Failures created in the last 24 h among the recent failures listed (max 15). */
  failed24h: number | null;
  failed24hCapped: boolean;
  podsNotReady: number | null;
  podsRestarted: number | null;
}

/** Counts for the top strip; null where the section failed. */
export function healthSummary(o: AdminOverview, nowMs: number): Health {
  const q = o.queues;
  const waiting = isSectionError(q) || q.error ? null : q.queues.reduce((n, x) => n + x.waiting, 0);
  const runs = isSectionError(o.runs) ? null : o.runs;
  const failed = runs?.recent_failures.filter((r) => {
    const t = toMs(r.finished_at) ?? toMs(r.created_at);
    return t != null && nowMs - t <= 86_400_000;
  });
  const deps = isSectionError(o.deployments) ? null : o.deployments.filter((d) => !isDeploymentError(d));
  const pods = deps?.flatMap((d) => (d as DeploymentInfo).pods) ?? null;
  return {
    waiting,
    activeRuns: runs ? runs.active.length : null,
    failed24h: failed ? failed.length : null,
    failed24hCapped: !!runs && !!failed && failed.length === runs.recent_failures.length && failed.length >= 15,
    podsNotReady: pods ? pods.filter((p) => !p.ready && !p.deleting).length : null,
    podsRestarted: pods ? pods.filter((p) => p.restarts > 0).length : null,
  };
}

/** The run's display name, or the start of its id. */
export function runLabel(r: Pick<AdminRun, "run_id" | "run_name">): string {
  const name = (r.run_name ?? "").split(">")[0].trim();
  return name || r.run_id;
}

/** Loose top-level files that hold the shared identifier-search cache. */
export function isResolverCache(name: string): boolean {
  return name.includes("resolver_cache");
}

/** "1".."365" -> the number; anything else -> null. */
export function parseCustomDays(raw: string): number | null {
  if (!/^\d+$/.test(raw.trim())) return null;
  const n = Number(raw.trim());
  return n >= 1 && n <= 365 ? n : null;
}
