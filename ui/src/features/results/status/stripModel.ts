/**
 * Status-strip model (SPEC.md §3.3) — pure derivations for the collapsed
 * one-liner, the slim 6-segment progress bar, the facts line and the
 * notes pill/expansion. Rendering lives in StatusStrip.tsx.
 */
import type { Molecule, Note, RunStatus, Stage } from "../viewmodel";

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

export interface RunProgress {
  stages: Stage[];
  molecules_done: number | null;
  molecules_total: number | null;
  typical: string | null;
  queue_position: number | null;
}

export function activeStepIndex(stages: Stage[]): number {
  return stages.findIndex((s) => s.status === "active");
}

/** Sum of known step durations, or null when none carry a duration. */
function sumDurations(stages: Stage[]): number | null {
  const ds = stages.map((s) => s.duration_s).filter((d): d is number => d != null);
  return ds.length ? ds.reduce((a, b) => a + b, 0) : null;
}

/**
 * The left-side line of the collapsed strip (SPEC.md §3.3 wording).
 * Returns null when there is nothing meaningful to say.
 */
export function leftLine(runStatus: RunStatus, progress: RunProgress): string | null {
  const { stages } = progress;
  switch (runStatus) {
    case "finished": {
      const total = sumDurations(stages);
      return total != null ? `Finished in ${humanDuration(total)}` : "Finished";
    }
    case "queued": {
      const pos = progress.queue_position;
      if (pos == null) return "Waiting in the queue";
      return `Waiting in the queue · ${pos === 1 ? "1 run ahead of yours" : `${pos} runs ahead of yours`}`;
    }
    case "running": {
      const i = activeStepIndex(stages);
      return i >= 0 ? `${stages[i].label}… step ${i + 1} of ${stages.length}` : "Working…";
    }
    case "failed": {
      const i = stages.findIndex((s) => s.status === "failed");
      if (i < 0) return null;
      const before = stages.slice(0, i + 1);
      const total = sumDurations(before);
      return `Stopped at step ${i + 1}: ${stages[i].label}${total != null ? `, after ${humanDuration(total)}` : ""}`;
    }
  }
}

/** "Read files 10 min · Find molecules 7 s · …" — the [Step timings ▾] expansion. */
export function timingsLine(stages: Stage[]): string | null {
  const parts = stages
    .filter((s) => s.duration_s != null && s.status !== "waiting")
    .map((s) => `${s.label} ${humanDuration(s.duration_s!)}`);
  return parts.length ? parts.join(" · ") : null;
}

/** Fill (0–1) of one progress segment; -1 → indeterminate (G2 fallback). */
export function stepFill(stage: Stage, progress: RunProgress): number {
  if (stage.status === "done" || stage.status === "failed") return 1;
  if (stage.status === "waiting") return 0;
  const { molecules_done, molecules_total } = progress;
  if (molecules_done != null && molecules_total != null && molecules_total > 0) {
    return Math.min(1, molecules_done / molecules_total);
  }
  return -1; // indeterminate sweep
}

export interface Facts {
  searched: string | null; // "12 of 25 molecules searched"
  elapsed: string | null; // "33 min elapsed"
  typical: string | null; // "usually 30–120 min"
  closeNote: string; // verbatim tail (SPEC.md §3.3)
}

/** Facts line parts for the running strip; null parts are omitted (G2). */
export function factsLine(runStatus: RunStatus, progress: RunProgress, elapsed_s: number | null): Facts | null {
  if (runStatus !== "running") return null;
  const { molecules_done, molecules_total, typical } = progress;
  return {
    searched:
      molecules_done != null && molecules_total != null
        ? `${molecules_done} of ${molecules_total} molecules searched`
        : null,
    // The active step's duration is already counted inside its stage; the
    // run-level elapsed_s wins when the backend provides it.
    elapsed: elapsed_s != null ? `${humanDuration(elapsed_s)} elapsed` : (() => {
      const t = sumDurations(progress.stages);
      return t != null ? `${humanDuration(t)} elapsed` : null;
    })(),
    typical: typical != null ? `usually ${typical}` : null,
    closeNote: "You can close this page; results stay at this link.",
  };
}

export interface NotesPill {
  attention: number;
  info: number;
  total: number;
  /** "3 notes: {title of most severe} and 2 more" (title truncated in CSS). */
  leadTitle: string;
  others: number;
  needsAttention: boolean;
}

/** Pill model; null when there are no notes at all. */
export function notesPill(notes: Note[]): NotesPill | null {
  if (notes.length === 0) return null;
  const sorted = sortedNotes(notes);
  const attention = notes.filter((n) => n.severity === "attention").length;
  return {
    attention,
    info: notes.length - attention,
    total: notes.length,
    leadTitle: sorted[0].title,
    others: notes.length - 1,
    needsAttention: attention > 0,
  };
}

/** Display order: attention first, then info (stable within a severity). */
export function sortedNotes(notes: Note[]): Note[] {
  return [...notes].sort((a, b) => (a.severity === b.severity ? 0 : a.severity === "attention" ? -1 : 1));
}

/** Cap of "Affects:" chips before "and N more" (SPEC.md §3.3). */
export const AFFECTS_VISIBLE = 6;

/**
 * "Affects" chips: segment ids → display names of known molecules.
 * Unknown ids are dropped — the chips hide entirely while backend gap G4
 * leaves affects empty/unresolvable (never internal seg_ ids).
 */
export function affectsNames(note: Note, molecules: Molecule[]): { id: string; name: string }[] {
  const byId = new Map(molecules.map((m) => [m.id, m.display_name]));
  return note.affects
    .filter((id) => byId.has(id))
    .map((id) => ({ id, name: byId.get(id)! }));
}

/** Footer wording for merged-away technical noise (SPEC.md §3.3). */
export function hiddenNotesFooter(hiddenCount: number): string | null {
  return hiddenCount > 0 ? `${hiddenCount} technical messages that don't affect results are in Technical details` : null;
}

/** The clickable tail of the footer. */
export const FOOTER_LINK_TEXT = "Technical details";
