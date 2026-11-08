/**
 * StatusStrip (SPEC.md §3.3): one card under the run header.
 * - finished: collapsed one-liner "✓ Finished in …" with [Step timings ▾]
 * - queued/running/failed: left line + slim 6-segment bar; running also
 *   gets the facts line with [Copy link]
 * - right: notes pill ("⚠ 1 ⓘ 2 · 3 notes: {title} and 2 more"), expanded
 *   as one line per note with "Affects:" chips (hidden until G4) and
 *   per-note disclosure. Open notes survive polling re-renders.
 */
import { useState, type ComponentType } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger, Tooltip, TooltipContent, TooltipTrigger, cn } from "@e-infra/design-system";
import { Check, ChevronDown, CircleX, Info, Link2, Loader2, TriangleAlert } from "lucide-react";
import type { Molecule, Note, RunStatus, Stage } from "../viewmodel";
import {
  AFFECTS_VISIBLE,
  affectsNames,
  factsLine,
  hiddenNotesFooter,
  humanDuration,
  leftLine,
  notesPill,
  sortedNotes,
  stepFill,
  timingsLine,
  type RunProgress,
} from "./stripModel";

function SlimBar({ stages, progress }: { stages: Stage[]; progress: RunProgress }) {
  return (
    <ol className="mt-2 flex gap-1" aria-label="Pipeline steps">
      {stages.map((s) => {
        const fill = stepFill(s, progress);
        const tip = s.duration_s != null ? `${s.label} · ${humanDuration(s.duration_s)}` : s.label;
        return (
          <li key={s.key} className="min-w-0 flex-1" aria-current={s.status === "active" ? "step" : undefined}>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="group" role="img" aria-label={`${s.label}: ${s.status}`}>
                  <div
                    className={cn(
                      "relative h-1.5 overflow-hidden rounded-full bg-(--vm-line)",
                      s.status === "failed" && "bg-(--vm-none)",
                    )}
                  >
                    {fill >= 0 && s.status !== "failed" && (
                      <div
                        className={cn("absolute inset-y-0 left-0 rounded-full", s.status === "done" ? "bg-(--vm-high)" : "bg-(--vm-info)")}
                        style={{ width: `${Math.round(fill * 100)}%` }}
                      />
                    )}
                    {fill === -1 && (
                      <div className="absolute inset-y-0 w-1/3 rounded-full bg-(--vm-info) motion-safe:animate-[sweep_1.2s_ease-in-out_infinite]" />
                    )}
                  </div>
                  <p className="mt-1 truncate text-center text-[12px] text-(--vm-muted) max-[560px]:hidden group-aria-[current=step]:font-semibold group-aria-[current=step]:text-(--vm-fg)">
                    {s.label}
                  </p>
                </div>
              </TooltipTrigger>
              <TooltipContent>{tip}</TooltipContent>
            </Tooltip>
          </li>
        );
      })}
      <style>{`@keyframes sweep { 0% { left: -33%; } 100% { left: 100%; } }`}</style>
    </ol>
  );
}

function NoteRow({ note, molecules, onSelect }: { note: Note; molecules: Molecule[]; onSelect: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const attention = note.severity === "attention";
  const Icon: ComponentType<{ size?: number; className?: string; "aria-hidden"?: boolean }> = attention ? TriangleAlert : Info;
  const chips = affectsNames(note, molecules);
  const shown = chips.slice(0, AFFECTS_VISIBLE);
  const extra = chips.length - shown.length;
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className="flex items-baseline gap-2">
        <CollapsibleTrigger className="flex min-w-0 flex-1 items-baseline gap-1.5 py-0.5 text-left" aria-expanded={open}>
          <Icon size={14} aria-hidden className={cn("shrink-0 translate-y-0.5", attention ? "text-(--vm-attention)" : "text-(--vm-info)")} />
          <span className="truncate text-sm font-medium text-(--vm-fg)">{note.title}</span>
          {note.raw_count > 1 && <span className="shrink-0 text-xs text-(--vm-muted)">{note.raw_count} messages</span>}
          <ChevronDown size={13} aria-hidden className={cn("shrink-0 translate-y-0.5 text-(--vm-muted) transition-transform", open && "rotate-180")} />
        </CollapsibleTrigger>
        {chips.length > 0 && (
          <span className="flex shrink-0 items-baseline gap-1 text-xs text-(--vm-muted)">
            Affects:
            {shown.map((c) => (
              <button key={c.id} type="button" onClick={() => onSelect(c.id)} className="text-(--vm-accent) underline-offset-2 hover:underline">
                {c.name}
              </button>
            ))}
            {extra > 0 && <span>and {extra} more</span>}
          </span>
        )}
      </div>
      <CollapsibleContent className="pb-1 pl-[21px]">
        <p className="text-sm text-(--vm-fg-2)">{note.body}</p>
        {note.action && <p className="mt-0.5 text-sm font-medium text-(--vm-fg)">What to do: {note.action}</p>}
      </CollapsibleContent>
    </Collapsible>
  );
}

export interface StatusStripProps {
  runStatus: RunStatus;
  progress: RunProgress;
  elapsedS: number | null;
  notes: Note[];
  hiddenNoteCount: number;
  molecules: Molecule[];
  onSelect: (id: string) => void;
  onCopyLink?: () => void;
  /** Opens the Technical-details fold (footer link, SPEC §3.3). */
  onOpenTechnical?: () => void;
}

export function StatusStrip({ runStatus, progress, elapsedS, notes, hiddenNoteCount, molecules, onSelect, onCopyLink, onOpenTechnical }: StatusStripProps) {
  const [timingsOpen, setTimingsOpen] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);
  const left = leftLine(runStatus, progress);
  const timings = timingsLine(progress.stages);
  const facts = factsLine(runStatus, progress, elapsedS);
  const pill = notesPill(notes);
  const footer = hiddenNotesFooter(hiddenNoteCount);
  const finished = runStatus === "finished";

  return (
    <section aria-label="Run progress" className="rounded-lg border border-(--vm-line) bg-(--vm-surface) px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {left && (
            <p
              className={cn(
                "flex items-center gap-1.5 text-sm",
                runStatus === "failed" ? "font-medium text-(--vm-none)" : runStatus === "running" ? "font-medium text-(--vm-fg)" : "text-(--vm-fg-2)",
              )}
              aria-live="polite"
            >
              {finished && <Check size={15} aria-hidden className="shrink-0 text-(--vm-high)" />}
              {runStatus === "running" && <Loader2 size={15} aria-hidden className="shrink-0 motion-safe:animate-spin text-(--vm-info)" />}
              {runStatus === "failed" && <CircleX size={15} aria-hidden className="shrink-0" />}
              {left}
              {finished && timings && (
                <button
                  type="button"
                  onClick={() => setTimingsOpen((v) => !v)}
                  aria-expanded={timingsOpen}
                  className="ml-1 inline-flex items-center gap-0.5 text-(--vm-accent) underline-offset-2 hover:underline"
                >
                  Step timings <ChevronDown size={13} aria-hidden className={cn("transition-transform", timingsOpen && "rotate-180")} />
                </button>
              )}
            </p>
          )}
          {finished && timingsOpen && timings && <p className="mt-1 pl-[21px] text-sm text-(--vm-muted)">{timings}</p>}
          {!finished && <SlimBar stages={progress.stages} progress={progress} />}
          {facts && (
            <p className="mt-2 text-sm text-(--vm-muted)">
              {[facts.searched, facts.elapsed, facts.typical].filter(Boolean).join(" · ")}
              {[facts.searched, facts.elapsed, facts.typical].some(Boolean) && " · "}
              {facts.closeNote}
              {onCopyLink && (
                <>
                  {" "}
                  <button type="button" onClick={onCopyLink} className="inline-flex items-center gap-0.5 text-(--vm-accent) underline-offset-2 hover:underline">
                    <Link2 size={13} aria-hidden /> Copy link
                  </button>
                </>
              )}
            </p>
          )}
        </div>

        {pill && (
          <button
            type="button"
            onClick={() => setNotesOpen((v) => !v)}
            aria-expanded={notesOpen}
            className={cn(
              "flex max-w-[55%] shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 text-[13px]",
              pill.needsAttention
                ? "border-(--vm-attention-line) bg-(--vm-attention-bg) text-(--vm-attention)"
                : "border-(--vm-line) bg-(--vm-surface-2) text-(--vm-fg-2)",
            )}
          >
            <span className="inline-flex items-center gap-1 whitespace-nowrap font-medium">
              {pill.attention > 0 && (
                <span className="inline-flex items-center gap-0.5">
                  <TriangleAlert size={13} aria-hidden /> {pill.attention}
                </span>
              )}
              {pill.info > 0 && (
                <span className="inline-flex items-center gap-0.5">
                  <Info size={13} aria-hidden /> {pill.info}
                </span>
              )}
            </span>
            <span className="truncate max-[560px]:hidden">
              {pill.total} {pill.total === 1 ? "note" : "notes"}: {pill.leadTitle}
              {pill.others > 0 && ` and ${pill.others} more`}
            </span>
            <ChevronDown size={13} aria-hidden className={cn("shrink-0 transition-transform", notesOpen && "rotate-180")} />
          </button>
        )}
      </div>

      {pill && notesOpen && (
        <div className="mt-2 border-t border-(--vm-line) pt-2">
          <div className="space-y-1">
            {sortedNotes(notes).map((n) => (
              <NoteRow key={n.id} note={n} molecules={molecules} onSelect={onSelect} />
            ))}
          </div>
          {footer && (
            <p className="mt-2 text-xs text-(--vm-muted)">
              {hiddenNoteCount} technical messages that don't affect results are in{" "}
              {onOpenTechnical ? (
                <button type="button" onClick={onOpenTechnical} className="text-(--vm-accent) underline-offset-2 hover:underline">
                  Technical details
                </button>
              ) : (
                "Technical details"
              )}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

export default StatusStrip;
