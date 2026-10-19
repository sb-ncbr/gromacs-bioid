/**
 * TanStack Query data hooks for the run-results page.
 *
 * ADAPTIVE POLLING (hard requirement — replaces the legacy 3s x 5 endpoint
 * storm that hammered every payload endpoint on a fixed timer):
 *
 *   - `useRunStatus` polls at 2500 ms only while the pipeline is live
 *     (pending/queued/running/created) and stops entirely (false) once the
 *     pipeline reaches a terminal state (success/failed/cancelled).
 *     staleTime 2000 ms.
 *   - Payload hooks (molecules / loading) refetch only while the pipeline
 *     status is not terminal.
 *   - Stage hooks (signatures / identifiers / verification) are disabled
 *     until their pipeline stage has appeared in `status.tasks` (i.e. the
 *     task has started), fetch once when the stage appears, keep polling
 *     only while the run is live, and never poll after terminal.
 *   - `useRunQueue` is enabled only while the pipeline is still pending.
 *
 * All response types come from the generated OpenAPI component schemas
 * (`lib/api/types`); no `any`.
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { api, endpoints } from "../../lib/api/client";
import type { components } from "../../lib/api/types";

/* ------------------------------------------------------------------ */
/* Generated response types (components.schemas)                       */
/* ------------------------------------------------------------------ */

export type RunStatusResponse = components["schemas"]["RunStatusResponse"];
export type RunSummaryResponse = components["schemas"]["RunSummaryResponse"];
export type MoleculeSummaryResponse = components["schemas"]["MoleculeSummaryResponse"];
export type LoadingInfoResponse = components["schemas"]["LoadingInfoResponse"];
export type SignaturesResponse = components["schemas"]["SignaturesResponse"];
export type IdentifiersResponse = components["schemas"]["IdentifiersResponse"];
export type VerificationResponse = components["schemas"]["VerificationResponse"];
export type RenderPathsResponse = components["schemas"]["RenderPathsResponse"];

/**
 * v3.137 additive render fields (API wave C) — present in the live API ahead
 * of baseline type regeneration, declared here per the QueueState pattern.
 *  - system_png / segment_pngs: static PNG previews (served via /files/)
 *  - total_atom_count: whole-system atom count for the interactivity gate
 */
export interface RenderPathsV37 {
  system_png?: string | null;
  segment_pngs?: Record<string, string>;
  total_atom_count?: number | null;
}

/** Atom ceiling for defaulting to interactive Mol* (user ruling 2026-10-19). */
export const ATOM_INTERACTIVE_LIMIT = 1_000_000;
export type RunFilesResponse = components["schemas"]["RunFilesResponse"];
export type TaskInfo = components["schemas"]["TaskInfo"];

/**
 * Queue endpoint response. Not yet present in the generated baseline
 * (additive API delta), so declared here — same shape as frontpage Recents.
 */
export interface QueueState {
  state?: string;
  position?: number | null;
  ahead?: number | null;
}

/* ------------------------------------------------------------------ */
/* Adaptive-polling primitives (pure — unit tested)                    */
/* ------------------------------------------------------------------ */

/** Poll cadence while the run is live. */
export const LIVE_POLL_MS = 2500;

/** Terminal pipeline states: polling must stop. */
export const TERMINAL_STATUSES: readonly string[] = ["success", "failed", "cancelled"];
/** Non-terminal (live) pipeline states. */
export const LIVE_STATUSES: readonly string[] = ["pending", "queued", "running", "created"];

export function isTerminal(status?: string | null): boolean {
  return !!status && (TERMINAL_STATUSES as readonly string[]).includes(status);
}

export function isLive(status?: string | null): boolean {
  return !!status && !isTerminal(status);
}

export function isPending(status?: string | null): boolean {
  return status === "pending" || status === "queued";
}

/** refetchInterval callback for the status query: 2500 while live, false at terminal. */
export function statusRefetchInterval(status?: string | null): number | false {
  return isLive(status) ? LIVE_POLL_MS : false;
}

/** refetchInterval for payload queries: poll only while pipeline is live. */
export function payloadRefetchInterval(live: boolean): number | false {
  return live ? LIVE_POLL_MS : false;
}

/** Extract pipeline.status from a RunStatusResponse (defensively). */
export function pipelineStatus(
  data: RunStatusResponse | null | undefined,
): string | null {
  return data?.pipeline?.status ?? null;
}

/** Status of a single task within the pipeline (null if not present). */
export function stageTaskStatus(
  data: RunStatusResponse | null | undefined,
  taskId: string,
): string | null {
  const tasks = data?.tasks;
  if (!Array.isArray(tasks)) return null;
  const t = tasks.find((x) => x.task_id === taskId);
  return t ? t.status : null;
}

/**
 * A stage "exists" for data-fetching purposes once its task has left the
 * `pending` state (i.e. it has appeared in the running pipeline). Unknown
 * or pending tasks return false so no request is made for a stage that has
 * not been reached yet.
 */
export function stageActive(
  data: RunStatusResponse | null | undefined,
  taskId: string,
): boolean {
  const s = stageTaskStatus(data, taskId);
  return s !== null && s !== "pending";
}

/* ------------------------------------------------------------------ */
/* Segment-meta helper (generated segment_meta is `unknown`)           */
/* ------------------------------------------------------------------ */

export interface SegmentMeta {
  type?: string | null;
  atom_count?: number | null;
  residue_count?: number | null;
}

/** Safely read one segment's meta from a MoleculeSummaryResponse. */
export function segmentMeta(
  molecules: MoleculeSummaryResponse | null | undefined,
  segment: string,
): SegmentMeta | null {
  const raw = molecules?.segment_meta;
  if (!raw || typeof raw !== "object") return null;
  const v = (raw as Record<string, unknown>)[segment];
  if (!v || typeof v !== "object") return null;
  return v as SegmentMeta;
}

/* ------------------------------------------------------------------ */
/* Hooks                                                               */
/* ------------------------------------------------------------------ */

/**
 * Pipeline status. Adaptive: 2500 ms while pending/queued/running,
 * stopped (false) once success/failed/cancelled. staleTime 2000 ms.
 */
export function useRunStatus(runId?: string): UseQueryResult<RunStatusResponse> {
  return useQuery({
    queryKey: ["runStatus", runId],
    queryFn: () => api.get<RunStatusResponse>(endpoints.runStatus(runId!)),
    enabled: !!runId,
    staleTime: 2000,
    retry: 1,
    refetchInterval: (query) => statusRefetchInterval(pipelineStatus(query.state.data ?? null)),
  });
}

/**
 * Run summary. The live summary may carry the user-supplied `run_name`
 * (set at submit time) which the generated baseline schema predates — hence
 * the additive optional field, still fully typed (no `any`).
 */
export type RunSummaryWithTitle = RunSummaryResponse & {
  run_name?: string | null;
};

/** Static run summary (title, counts). Fetched once; no polling. */
export function useRunSummary(runId?: string): UseQueryResult<RunSummaryWithTitle> {
  return useQuery({
    queryKey: ["runSummary", runId],
    queryFn: () => api.get<RunSummaryWithTitle>(endpoints.run(runId!)),
    enabled: !!runId,
    staleTime: 30_000,
    retry: 1,
  });
}

/** Molecule summary (segments + segment_meta). Refetch only while live. */
export function useRunMolecules(runId: string | undefined, live: boolean) {
  return useQuery({
    queryKey: ["runMolecules", runId],
    queryFn: () => api.get<MoleculeSummaryResponse>(endpoints.runMolecules(runId!)),
    enabled: !!runId,
    retry: 1,
    refetchInterval: () => payloadRefetchInterval(live),
  });
}

/** Loading info (strategy card + attempts). Refetch only while live. */
export function useRunLoading(runId: string | undefined, live: boolean) {
  return useQuery({
    queryKey: ["runLoading", runId],
    queryFn: () => api.get<LoadingInfoResponse>(endpoints.runLoading(runId!)),
    enabled: !!runId,
    retry: 1,
    refetchInterval: () => payloadRefetchInterval(live),
  });
}

/** Run file list. Refetch only while live. */
export function useRunFiles(runId: string | undefined, live: boolean) {
  return useQuery({
    queryKey: ["runFiles", runId],
    queryFn: () => api.get<RunFilesResponse>(endpoints.runFiles(runId!)),
    enabled: !!runId,
    retry: 1,
    refetchInterval: () => payloadRefetchInterval(live),
  });
}

/** Render paths (mmCIF locations for the Mol* viewer). Refetch only while live. */
export function useRunRender(runId: string | undefined, live: boolean) {
  return useQuery({
    queryKey: ["runRender", runId],
    queryFn: () => api.get<RenderPathsResponse>(endpoints.runRender(runId!)),
    enabled: !!runId,
    retry: 1,
    refetchInterval: () => payloadRefetchInterval(live),
  });
}

/**
 * Signatures. Enabled only once the `generate_signatures` stage has
 * appeared in status.tasks; polls while live, never after terminal.
 */
export function useRunSignatures(
  runId: string | undefined,
  segment: string,
  stageOn: boolean,
  live: boolean,
) {
  return useQuery({
    queryKey: ["runSignatures", runId, segment],
    queryFn: () =>
      api.get<SignaturesResponse>(endpoints.runSignatures(runId!), { segment }),
    enabled: !!runId && stageOn,
    retry: 1,
    refetchInterval: () => payloadRefetchInterval(live),
  });
}

/**
 * Identifiers. Enabled only once the `identify_molecules` stage has
 * appeared in status.tasks; polls while live, never after terminal.
 */
export function useRunIdentifiers(
  runId: string | undefined,
  segment: string,
  stageOn: boolean,
  live: boolean,
) {
  return useQuery({
    queryKey: ["runIdentifiers", runId, segment],
    queryFn: () =>
      api.get<IdentifiersResponse>(endpoints.runIdentifiers(runId!), { segment }),
    enabled: !!runId && stageOn,
    retry: 1,
    refetchInterval: () => payloadRefetchInterval(live),
  });
}

/**
 * Verification hits. Enabled only once the `verify_results` stage has
 * appeared in status.tasks; polls while live, never after terminal.
 */
export function useRunVerification(
  runId: string | undefined,
  segment: string,
  stageOn: boolean,
  live: boolean,
) {
  return useQuery({
    queryKey: ["runVerification", runId, segment],
    queryFn: () =>
      api.get<VerificationResponse>(endpoints.runVerification(runId!), { segment }),
    enabled: !!runId && stageOn,
    retry: 1,
    refetchInterval: () => payloadRefetchInterval(live),
  });
}

/** Queue position. Enabled only while the pipeline is still pending. */
export function useRunQueue(runId: string | undefined, pending: boolean) {
  return useQuery({
    queryKey: ["runQueue", runId],
    queryFn: () => api.get<QueueState>(endpoints.runQueue(runId!)),
    enabled: !!runId && pending,
    retry: 0,
    refetchInterval: LIVE_POLL_MS,
  });
}
