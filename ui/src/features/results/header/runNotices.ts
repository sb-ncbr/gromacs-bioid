/**
 * Notices above the results (2026-11-18): failed lookups a rerun could fix,
 * an automatic retry waiting, attempts so far, and links between reruns.
 * Pure; tested in runNotices.test.ts.
 */
import type { components } from "../../../lib/api/types";
import { serviceLabel } from "../viewmodel/notes";

type Status = components["schemas"]["RunStatusResponse"];
export type IncompleteItem = components["schemas"]["IncompleteItem"];

const REASONS: Record<string, string> = {
  server_error: "server error",
  rate_limited: "busy",
  timeout: "no answer in time",
  connection: "unreachable",
  budget: "out of time",
};

const FINISHED = new Set(["success", "failed", "cancelled", "timeout", "error"]);

export interface RunNotices {
  supersededBy: string | null;
  rerunOf: string | null;
  /** waiting for the next automatic attempt */
  retry: string | null;
  /** finished after automatic retries */
  attempts: string | null;
  /** failed lookups of a finished run, one line per service */
  incomplete: string[];
}

function gapLine(g: IncompleteItem): string {
  const name = g.code === "identifier_resolver_failed" ? `${serviceLabel(g.service)} (${g.service})` : g.service;
  const n = g.count === 1 ? "1 lookup" : `${g.count} lookups`;
  return `${name}: ${REASONS[g.reason] ?? g.reason}, ${n}`;
}

function clock(unixS: number, nowMs: number): string {
  const ms = unixS * 1000;
  if (ms <= nowMs) return "shortly";
  const d = new Date(ms);
  const time = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return new Date(nowMs).toDateString() === d.toDateString() ? `at ${time}` : `on ${d.toLocaleDateString()} at ${time}`;
}

export function runNotices(s: Status | null | undefined, nowMs: number): RunNotices {
  const out: RunNotices = { supersededBy: null, rerunOf: null, retry: null, attempts: null, incomplete: [] };
  if (!s) return out;
  out.supersededBy = s.superseded_by ?? null;
  out.rerunOf = s.rerun_of ?? null;
  const retry = s.retry;
  if (retry) {
    const what = retry.reason === "worker_lost"
      ? `Attempt ${retry.attempt} of ${retry.max_attempts} was interrupted (a worker stopped).`
      : `Attempt ${retry.attempt} of ${retry.max_attempts} could not reach every database.`;
    out.retry = `${what} The next attempt starts ${clock(retry.at, nowMs)}; this page updates by itself.`;
  }
  const status = s.pipeline?.status ?? "";
  const earlier = s.attempts?.length ?? 0;
  if (earlier > 0 && FINISHED.has(status)) out.attempts = `Finished on attempt ${earlier + 1}.`;
  if (FINISHED.has(status) && status !== "cancelled") out.incomplete = (s.incomplete ?? []).map(gapLine);
  return out;
}
