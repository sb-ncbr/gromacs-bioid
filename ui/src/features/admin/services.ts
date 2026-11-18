/** Pure helpers for the Services section (tested in services.test.ts). */
import type { ServiceRow } from "../../lib/api/admin";
import type { Tone } from "./format";

export type StageFilter = "all" | "identify" | "verify";

const STAGE_OF: Record<Exclude<StageFilter, "all">, string> = {
  identify: "identify_molecules",
  verify: "verify_results",
};

/** "db:chembl_struct@sim" -> database "chembl_struct (similar)"; "http:host" -> web "host". */
export function serviceLabel(service: string): { kind: "database" | "web" | "other"; name: string } {
  if (service.startsWith("db:")) {
    const name = service.slice(3);
    return { kind: "database", name: name.endsWith("@sim") ? `${name.slice(0, -4)} (similar)` : name };
  }
  if (service.startsWith("http:")) return { kind: "web", name: service.slice(5) };
  return { kind: "other", name: service };
}

/** Rows of one stage, or every stage merged per service. */
export function rowsFor(rows: ServiceRow[], stage: StageFilter): ServiceRow[] {
  if (stage !== "all") return rows.filter((r) => r.stage === STAGE_OF[stage]);
  const by = new Map<string, ServiceRow>();
  for (const r of rows) {
    const prev = by.get(r.service);
    if (!prev) {
      by.set(r.service, { ...r, stage: "all", outcomes: { ...r.outcomes } });
      continue;
    }
    const timedPrev = prev.mean_s != null ? prev.calls : 0;
    const timedNew = r.mean_s != null ? r.calls : 0;
    const outcomes = { ...prev.outcomes };
    for (const [k, n] of Object.entries(r.outcomes)) outcomes[k] = (outcomes[k] ?? 0) + n;
    const calls = prev.calls + r.calls;
    const errors = prev.errors + r.errors;
    by.set(r.service, {
      ...prev,
      calls,
      cached: prev.cached + r.cached,
      errors,
      error_share: calls ? errors / calls : null,
      retries: prev.retries + r.retries,
      outcomes,
      mean_s: timedPrev + timedNew
        ? ((prev.mean_s ?? 0) * timedPrev + (r.mean_s ?? 0) * timedNew) / (timedPrev + timedNew)
        : null,
      // percentiles cannot be merged exactly: keep the slower stage's
      p50_s: maxOrNull(prev.p50_s, r.p50_s),
      p95_s: maxOrNull(prev.p95_s, r.p95_s),
    });
  }
  return [...by.values()].sort((a, b) => b.errors - a.errors || b.calls - a.calls || a.service.localeCompare(b.service));
}

function maxOrNull(a: number | null, b: number | null): number | null {
  if (a == null) return b;
  if (b == null) return a;
  return Math.max(a, b);
}

export function errorTone(share: number | null, calls: number): Tone {
  if (share == null || calls === 0) return "muted";
  if (calls >= 10 && share >= 0.5) return "error";
  if (share >= 0.05) return "warn";
  return "ok";
}

/** 0.12 -> "0.1 s", 4 -> "4 s", 95 -> "1.6 min", 7200 -> "2 h"; Infinity -> "> 12 h". */
export function formatSeconds(s: number | null): string {
  if (s == null || Number.isNaN(s)) return "—";
  if (!Number.isFinite(s)) return "> 12 h";
  if (s < 1) return `${s.toFixed(1)} s`;
  if (s < 60) return `${Math.round(s)} s`;
  if (s < 3600) return `${(s / 60).toFixed(1).replace(/\.0$/, "")} min`;
  return `${(s / 3600).toFixed(1).replace(/\.0$/, "")} h`;
}

/** Error outcomes only, most frequent first: "http_5xx 12, error:timeout 3". */
export function errorBreakdown(outcomes: Record<string, number>): string {
  return Object.entries(outcomes)
    .filter(([k]) => k.startsWith("error") || k === "http_5xx" || k === "http_429")
    .sort((a, b) => b[1] - a[1])
    .map(([k, n]) => `${k.replace(/^error:/, "")} ${n}`)
    .join(", ");
}
