/** Pure helpers for the queue cards (tested in lanes.test.ts). */
import type { LaneCard, RetryPolicy } from "../../lib/api/admin";
import type { Tone } from "./format";

/** The card's state at a glance. */
export function laneHealth(card: LaneCard): { tone: Tone; text: string } {
  const waiting = card.waiting ?? 0;
  if (card.pool?.error) return { tone: "error", text: "worker pool unavailable" };
  if (card.pool && card.pool.crashing > 0)
    return { tone: "error", text: `${card.pool.crashing} worker${card.pool.crashing === 1 ? "" : "s"} failing` };
  if (waiting > 0 && card.consumers.length === 0) return { tone: "error", text: "waiting runs, no workers" };
  if (card.paused) return { tone: "warn", text: "paused" };
  if (card.running > 0 || waiting > 0) return { tone: "info", text: "busy" };
  if (card.consumers.length === 0) return { tone: "muted", text: "no workers" };
  return { tone: "ok", text: "idle" };
}

/** "8/8 ready · bat3-validation-api@sha256:…" */
export function poolText(pool: LaneCard["pool"]): string {
  if (!pool) return "no worker deployment";
  if (pool.error) return pool.error;
  const ready = `${pool.ready ?? 0}/${pool.replicas ?? 0} ready`;
  return pool.image ? `${ready} · ${pool.image}` : ready;
}

export function policySummary(p: RetryPolicy | null): string {
  if (!p) return "";
  if (!p.enabled) return "Automatic retries off.";
  const on = [p.incomplete && "incomplete runs", p.worker_lost && "lost workers"].filter(Boolean).join(" and ");
  if (!on) return "Automatic retries on, but no failure kind selected.";
  return `Retries ${on}: up to ${p.max_attempts} attempts, ${p.delay_minutes} min apart.`;
}

/** Error text for a policy draft, or null when it can be saved (limits as in retries.py). */
export function policyError(p: RetryPolicy): string | null {
  if (!Number.isInteger(p.max_attempts) || p.max_attempts < 1 || p.max_attempts > 10)
    return "Attempts must be a whole number from 1 to 10.";
  if (!Number.isInteger(p.delay_minutes) || p.delay_minutes < 1 || p.delay_minutes > 1440)
    return "Delay must be a whole number of minutes from 1 to 1440.";
  return null;
}

/** Runs of the lane by status, busiest first, for a compact line. */
export function runCounts(runs: Record<string, number>): string {
  const order = ["running", "queued", "retry_scheduled", "failed", "success"];
  const label: Record<string, string> = { retry_scheduled: "waiting to retry" };
  const rank = (s: string) => (order.includes(s) ? order.indexOf(s) : order.length);
  return Object.entries(runs)
    .sort((a, b) => rank(a[0]) - rank(b[0]) || b[1] - a[1])
    .map(([s, n]) => `${n} ${label[s] ?? s}`)
    .join(" · ");
}
