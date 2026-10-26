/**
 * StatusStrip — the 6-step progress bar + facts line + notes pill
 * (SPEC.md §3.3). Steps come from viewmodel/steps.ts, notes from
 * viewmodel/notes.ts through the adapter; this component only renders.
 */
import { useState, type ComponentType } from "react";
import { Badge, Popover, PopoverContent, PopoverTrigger, cn } from "@e-infra/design-system";
import { Check, Circle, CircleX, Info, Loader2, TriangleAlert } from "lucide-react";
import type { Molecule, Note, RunStatus, Stage, StageStatus } from "../viewmodel";
import { affectsNames, factsLine, humanDuration, notesPill } from "./stripModel";

const STEP_ICON: Record<StageStatus, ComponentType<{ size?: number; className?: string; "aria-hidden"?: boolean }>> = {
  done: Check,
  active: Loader2,
  waiting: Circle,
  failed: CircleX,
};

const STEP_COLOR: Record<StageStatus, string> = {
  done: "text-(--vm-high)",
  active: "text-(--vm-info)",
  waiting: "text-(--vm-muted)",
  failed: "text-(--vm-none)",
};

function Step({ stage, last }: { stage: Stage; last: boolean }) {
  const Icon = STEP_ICON[stage.status];
  return (
    <li className="flex min-w-0 flex-1 items-center" aria-current={stage.status === "active" ? "step" : undefined}>
      <div className="flex min-w-0 flex-col items-start gap-0.5">
        <span className="flex items-center gap-1.5">
          <Icon
            size={15}
            aria-hidden
            className={cn("shrink-0", STEP_COLOR[stage.status], stage.status === "active" && "motion-safe:animate-spin")}
          />
          <span
            className={cn(
              "truncate text-[13px]",
              stage.status === "active" ? "font-semibold text-(--vm-fg)" : stage.status === "waiting" ? "text-(--vm-muted)" : "text-(--vm-fg-2)",
            )}
          >
            {stage.label}
          </span>
        </span>
        {stage.duration_s != null && stage.status !== "waiting" && (
          <span className="pl-[21px] text-xs tabular-nums text-(--vm-muted)">
            {stage.status === "active" ? `${humanDuration(stage.duration_s)} so far` : humanDuration(stage.duration_s)}
          </span>
        )}
      </div>
      {!last && <span aria-hidden className="mx-2 h-px flex-1 self-start mt-2.5 bg-(--vm-line)" />}
    </li>
  );
}

function NoteCard({ note, molecules }: { note: Note; molecules: Molecule[] }) {
  const names = affectsNames(note, molecules); // chips hide until G4 lands
  const attention = note.severity === "attention";
  const Icon = attention ? TriangleAlert : Info;
  return (
    <div
      className={cn(
        "rounded-md border p-3",
        attention ? "border-(--vm-attention-line) bg-(--vm-attention-bg)" : "border-(--vm-info-line) bg-(--vm-info-bg)",
      )}
    >
      <p className={cn("flex items-center gap-1.5 text-sm font-semibold", attention ? "text-(--vm-attention)" : "text-(--vm-info)")}>
        <Icon size={15} aria-hidden />
        {note.title}
      </p>
      <p className="mt-1 text-sm text-(--vm-fg-2)">{note.body}</p>
      {note.action && <p className="mt-1 text-sm font-medium text-(--vm-fg)">What to do: {note.action}</p>}
      {names.length > 0 && (
        <p className="mt-1.5 flex flex-wrap items-center gap-1 text-xs text-(--vm-muted)">
          Affects:
          {names.map((n) => (
            <Badge key={n} variant="secondary" className="text-xs">
              {n}
            </Badge>
          ))}
        </p>
      )}
    </div>
  );
}

export interface StatusStripProps {
  runStatus: RunStatus;
  stages: Stage[];
  notes: Note[];
  molecules: Molecule[];
  errorTitle?: string | null;
}

export function StatusStrip({ runStatus, stages, notes, molecules, errorTitle }: StatusStripProps) {
  const [open, setOpen] = useState(false);
  const facts = factsLine(runStatus, stages, errorTitle);
  const pill = notesPill(notes);
  const sorted = [...notes].sort((a, b) => (a.severity === b.severity ? 0 : a.severity === "attention" ? -1 : 1));

  return (
    <div aria-label="Run progress" className="rounded-lg border border-(--vm-line) bg-(--vm-surface) px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <ol className="flex min-w-0 flex-1 items-stretch overflow-x-auto">
          {stages.map((s, i) => (
            <Step key={s.key} stage={s} last={i === stages.length - 1} />
          ))}
        </ol>
        {pill && (
          <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                className={cn(
                  "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 text-[13px] font-medium",
                  pill.needsAttention
                    ? "border-(--vm-attention-line) bg-(--vm-attention-bg) text-(--vm-attention)"
                    : "border-(--vm-line) bg-(--vm-surface-2) text-(--vm-fg-2)",
                )}
              >
                {pill.needsAttention ? <TriangleAlert size={14} aria-hidden /> : <Info size={14} aria-hidden />}
                {pill.label}
              </button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-[min(420px,90vw)]">
              <p className="mb-2 text-xs uppercase tracking-wide text-(--vm-muted)">
                {pill.attention > 0 ? `${pill.attention} need${pill.attention === 1 ? "s" : ""} attention` : "No action needed"}
              </p>
              <div className="max-h-[50vh] space-y-2 overflow-y-auto">
                {sorted.map((n) => (
                  <NoteCard key={n.id} note={n} molecules={molecules} />
                ))}
              </div>
            </PopoverContent>
          </Popover>
        )}
      </div>
      {facts && (
        <p className={cn("mt-2 text-sm", runStatus === "failed" ? "text-(--vm-none)" : "text-(--vm-muted)")} aria-live="polite">
          {facts}
        </p>
      )}
    </div>
  );
}

export default StatusStrip;
