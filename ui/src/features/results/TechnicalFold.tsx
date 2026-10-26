/**
 * TechnicalDetails — the single collapsed fold at the bottom (SPEC §3.6).
 * Subtitle: "How your files were read, step timings, molecule descriptions,
 * every search and candidate, raw messages, logs and settings". Seven
 * entries open the existing developer views unchanged — this is where
 * internal ids (seg_, resolvers, task ids) legitimately live.
 */
import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger, cn } from "@e-infra/design-system";
import { ChevronDown } from "lucide-react";
import type { RunStatusResponse, RunSummaryWithTitle, LoadingInfoResponse } from "./hooks";
import type { TechnicalEntry } from "./viewmodel";
import TaskBar from "./TaskBar";
import WarningsPanel from "./WarningsPanel";
import OverviewTab from "./OverviewTab";
import InputFilesTab from "./InputFilesTab";
import SignaturesTab from "./SignaturesTab";
import IdentifiersTab from "./IdentifiersTab";
import VerificationTab from "./VerificationTab";

export const FOLD_SUBTITLE =
  "How your files were read, step timings, molecule descriptions, every search and candidate, raw messages, logs and settings";

export interface TechnicalFoldProps {
  entries: TechnicalEntry[];
  runId: string;
  /** Selected molecule (segment id) for the per-segment developer views. */
  segment: string;
  segments: string[];
  onSegmentChange: (segment: string) => void;
  status: RunStatusResponse | null;
  summary: RunSummaryWithTitle | null;
  loading: LoadingInfoResponse | null;
  files: string[];
  signatures: unknown | null;
  identifiers: unknown | null;
  verification: unknown | null;
}

export interface TechnicalFoldHandle {
  open: () => void;
}

export const TechnicalFold = forwardRef<TechnicalFoldHandle, TechnicalFoldProps>(function TechnicalFold({
  entries,
  runId,
  segment,
  segments,
  onSegmentChange,
  status,
  summary,
  loading,
  files,
  signatures,
  identifiers,
  verification,
}, ref) {
  const [open, setOpen] = useState(false);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  useImperativeHandle(ref, () => ({
    open: () => {
      setOpen(true);
      setTimeout(() => rootRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    },
  }), []);

  const render = (key: string) => {
    switch (key) {
      case "input":
        return (
          <InputFilesTab
            runId={runId}
            loading={loading}
            inputFiles={status?.pipeline?.input_files ?? null}
            files={files}
          />
        );
      case "timings":
        return <TaskBar tasks={status?.tasks ?? []} onGroupClick={() => {}} />;
      case "signatures":
        return (
          <SignaturesTab
            segment={segment}
            onSegmentChange={onSegmentChange}
            segments={segments}
            signatures={signatures as never}
          />
        );
      case "searches":
        return (
          <IdentifiersTab
            segment={segment}
            onSegmentChange={onSegmentChange}
            segments={segments}
            identifiers={identifiers as never}
          />
        );
      case "candidates":
        return (
          <VerificationTab
            segment={segment}
            segments={segments}
            onSegmentChange={onSegmentChange}
            verification={verification as never}
            onJumpToIdentifiers={() => setActiveKey("searches")}
          />
        );
      case "messages":
        return (
          <WarningsPanel
            warnings={status?.warnings ?? []}
            criticalErrors={status?.critical_errors ?? []}
          />
        );
      case "logs":
        return <OverviewTab runId={runId} status={status} summary={summary} />;
      default:
        return null;
    }
  };

  return (
    <Collapsible ref={rootRef} open={open} onOpenChange={setOpen} className="mt-5 rounded-lg border border-(--vm-line) bg-(--vm-surface)">
      <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left" aria-expanded={open}>
        <span>
          <span className="text-sm font-semibold text-(--vm-fg)">Technical details</span>
          <span className="mt-0.5 block text-xs text-(--vm-muted)">{FOLD_SUBTITLE}</span>
        </span>
        <ChevronDown size={16} aria-hidden className={cn("shrink-0 text-(--vm-muted) transition-transform", open && "rotate-180")} />
      </CollapsibleTrigger>
      <CollapsibleContent className="border-t border-(--vm-line) px-4 pb-4">
        <div className="flex flex-wrap gap-1 pt-3" role="tablist" aria-label="Technical detail sections">
          {entries.map((e) => (
            <button
              key={e.key}
              type="button"
              role="tab"
              aria-selected={activeKey === e.key}
              onClick={() => setActiveKey(activeKey === e.key ? null : e.key)}
              className={cn(
                "rounded-full border px-3 py-1 text-[13px]",
                activeKey === e.key
                  ? "border-(--vm-accent) bg-(--vm-accent-bg) text-(--vm-accent)"
                  : "border-(--vm-line) text-(--vm-fg-2) hover:bg-(--vm-surface-2)",
              )}
            >
              {e.title}
            </button>
          ))}
        </div>
        {activeKey && (
          <div className="mt-3">
            <p className="mb-2 text-xs text-(--vm-muted)">{entries.find((e) => e.key === activeKey)?.desc}</p>
            {render(activeKey)}
          </div>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
});

export default TechnicalFold;
