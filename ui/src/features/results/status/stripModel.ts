/**
 * Status-strip model (SPEC.md §3.3) — pure facts line, notes pill and
 * duration formatting for the 6-step progress bar. Vue stage data comes
 * from viewmodel/steps.ts; this module only words it.
 */
import type { Molecule, Note, RunStatus, Stage, StageStatus } from "../viewmodel";

/** "42 s" / "3 min" / "1 h 5 min". */
export function humanDuration(seconds: number): string {
  const s = Math.round(seconds);
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return m === 1 ? "1 min" : `${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return rest === 0 ? `${h} h` : `${h} h ${rest} min`;
}

/** The currently active step index (0-based), or -1 when none. */
export function activeStepIndex(stages: Stage[]): number {
  return stages.findIndex((s) => s.status === "active");
}

/**
 * The one-line facts under/next to the strip — mirrors the run status:
 * queued/running/finished/failed.
 */
export function factsLine(runStatus: RunStatus, stages: Stage[], errorTitle?: string | null): string | null {
  const step = (s: Stage | undefined, i: number) => `Step ${i + 1} of ${stages.length} · ${s?.label ?? ""}`;
  switch (runStatus) {
    case "queued":
      return "Waiting for a free worker — your run starts automatically";
    case "running": {
      const i = activeStepIndex(stages);
      if (i < 0) return "Working…";
      const cur = stages[i];
      const elapsed = cur.duration_s != null ? ` · ${humanDuration(cur.duration_s)}` : "";
      return `${step(cur, i)}${elapsed}`;
    }
    case "finished": {
      const done = stages.filter((s) => s.status === "done").map((s) => s.duration_s);
      const valid = done.filter((d): d is number => d != null);
      if (valid.length === 0) return "Finished";
      return `Finished in ${humanDuration(valid.reduce((a, b) => a + b, 0))}`;
    }
    case "failed": {
      const i = stages.findIndex((s) => s.status === "failed");
      const label = i >= 0 ? stages[i].label : null;
      return label ? `Stopped at ${label}${errorTitle ? ` — ${errorTitle}` : ""}` : null;
    }
  }
}

export interface NotesPill {
  total: number;
  attention: number;
  /** Button label: "3 notes" — icon carries the severity. */
  label: string;
  needsAttention: boolean;
}

/** Pill model for the "N notes" button on the strip; null when no notes. */
export function notesPill(notes: Note[]): NotesPill | null {
  if (notes.length === 0) return null;
  const attention = notes.filter((n) => n.severity === "attention").length;
  return {
    total: notes.length,
    attention,
    label: notes.length === 1 ? "1 note" : `${notes.length} notes`,
    needsAttention: attention > 0,
  };
}

/**
 * "Affects" chips: segment ids → display names of the known molecules.
 * Unknown ids are dropped — the chips hide entirely while backend gap G4
 * leaves affects empty or unresolvable (never show internal seg_ ids).
 */
export function affectsNames(note: Note, molecules: Molecule[]): string[] {
  const byId = new Map(molecules.map((m) => [m.id, m.display_name]));
  return note.affects.map((id) => byId.get(id)).filter((n): n is string => n != null);
}

/** Status icon+wording key for a step (rendering owns the glyphs). */
export const STEP_STATUS_WORD: Record<StageStatus, string> = {
  done: "done",
  active: "in progress",
  waiting: "waiting",
  failed: "failed",
};
