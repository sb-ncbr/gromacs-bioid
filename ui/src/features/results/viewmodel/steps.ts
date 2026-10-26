/**
 * Pipeline tasks → the six user-facing steps (SPEC.md §3.3 mapping table,
 * COPY.md §2.1 labels).
 */
import type { Stage, StageKey, StageStatus } from "./types";
import { STAGE_LABELS } from "./labels";

/** Task shape (subset of the generated TaskInfo; structural). */
export interface TaskView {
  task_id?: string;
  status?: string;
  started_at?: string | null;
  finished_at?: string | null;
}

/** Step key → the pipeline task ids it summarises. */
export const STAGE_TASKS: Record<StageKey, string[]> = {
  read: ["discover_input", "load_simulation", "repair_topology", "unwrap_periodic_boundaries"],
  find: ["analyze_universe"],
  describe: ["generate_signatures"],
  search: ["identify_molecules"],
  check: ["verify_results"],
  save: ["export_results"],
};

const ORDER: StageKey[] = ["read", "find", "describe", "search", "check", "save"];

/** Task statuses that leave the stage complete ("warning still counts as done"). */
const DONE_STATES = new Set(["success", "warning", "skipped"]);

function statusOf(tasks: TaskView[]): StageStatus {
  if (tasks.some((t) => t.status === "failed")) return "failed";
  if (tasks.some((t) => t.status === "running")) return "active";
  if (tasks.length > 0 && tasks.every((t) => DONE_STATES.has(t.status ?? ""))) return "done";
  return "waiting";
}

function ms(value: string | null | undefined): number | null {
  if (!value) return null;
  const t = Date.parse(value);
  return Number.isNaN(t) ? null : t;
}

function duration(tasks: TaskView[], status: StageStatus, now: number): number | null {
  const started = tasks.map((t) => ms(t.started_at)).filter((t): t is number => t != null);
  if (started.length === 0) return null;
  const begin = Math.min(...started);
  if (status === "active") return Math.max(0, Math.round((now - begin) / 1000));
  if (status === "done" || status === "failed") {
    const finished = tasks.map((t) => ms(t.finished_at)).filter((t): t is number => t != null);
    if (finished.length === 0) return null;
    const end = Math.max(...finished);
    return end >= begin ? Math.round((end - begin) / 1000) : null;
  }
  return null;
}

/**
 * Summarise pipeline tasks into the six steps. Unknown/absent tasks leave
 * the step waiting. `now` only matters while a step is active.
 */
export function steps(tasks: TaskView[] | null | undefined, now: number): Stage[] {
  const list = Array.isArray(tasks) ? tasks : [];
  return ORDER.map((key) => {
    const ids = STAGE_TASKS[key];
    const own = list.filter((t) => t.task_id != null && ids.includes(t.task_id));
    const status = statusOf(own);
    return {
      key,
      label: STAGE_LABELS[key],
      status,
      duration_s: duration(own, status, now),
    };
  });
}
