/**
 * Distribution bar + filter key (SPEC.md §3.4: the bar doubles as the filter).
 * Pure presentation; counts and active bucket come from the parent.
 */
import { ToggleGroup, ToggleGroupItem, Tooltip, TooltipContent, TooltipTrigger, cn } from "@e-infra/design-system";
import type { Bucket } from "./moleculeList";
import type { RunStatus } from "../viewmodel";

const BAR_COLORS: Record<Bucket, string> = {
  high: "bg-(--vm-high)",
  medium: "bg-(--vm-medium)",
  low: "bg-(--vm-low)",
  none: "bg-(--vm-none)",
  searched: "bg-(--vm-high)",
  searching: "bg-(--vm-info)",
  waiting: "bg-(--vm-progress-track)",
  not_searched: "bg-(--vm-none)",
};

const DONE_TOOLTIPS: Record<string, string> = {
  high: "Show only: High confidence or exact",
  medium: "Show only: Medium confidence",
  low: "Show only: Low confidence",
  none: "Show only: Not identified",
};

export function keyLabel(bucket: Bucket, n: number): string {
  const words: Record<Bucket, string> = {
    high: "High",
    medium: "Medium",
    low: "Low",
    none: "None",
    searched: "Searched",
    searching: "Searching",
    waiting: "Waiting",
    not_searched: "Not searched",
  };
  return `${n} ${words[bucket]}`;
}

export interface DistributionBarProps {
  counts: Partial<Record<Bucket, number>>;
  order: Bucket[];
  active: Bucket | null;
  runStatus: RunStatus;
  onToggle: (bucket: Bucket | null) => void;
}

export function DistributionBar({ counts, order, active, runStatus, onToggle }: DistributionBarProps) {
  const total = order.reduce((n, b) => n + (counts[b] ?? 0), 0);
  if (total === 0) return null;
  const visible = order.filter((b) => (counts[b] ?? 0) > 0);
  return (
    <div>
      <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-(--vm-progress-track)" role="img"
        aria-label={visible.map((b) => keyLabel(b, counts[b] ?? 0)).join(", ")}>
        {visible.map((b) => (
          <div
            key={b}
            className={cn("h-full", BAR_COLORS[b])}
            style={{ width: `${(((counts[b] ?? 0) / total) * 100).toFixed(2)}%` }}
          />
        ))}
      </div>
      <ToggleGroup
        type="single"
        value={active ?? ""}
        onValueChange={(v) => onToggle((v || null) as Bucket | null)}
        className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-(--vm-muted)"
      >
        {visible.map((b) => (
          <Tooltip key={b}>
            <TooltipTrigger asChild>
              <ToggleGroupItem
                value={b}
                aria-label={keyLabel(b, counts[b] ?? 0)}
                className={cn(
                  "h-auto px-1 py-0.5 text-xs font-normal tabular-nums",
                  active != null && active !== b && "opacity-45",
                )}
              >
                <span className={cn("mr-1 inline-block size-2 rounded-full", BAR_COLORS[b])} aria-hidden />
                {keyLabel(b, counts[b] ?? 0)}
              </ToggleGroupItem>
            </TooltipTrigger>
            <TooltipContent>
              {runStatus === "finished" ? (DONE_TOOLTIPS[b] ?? "Show only this group") : `Show only: ${keyLabel(b, counts[b] ?? 0).replace(/^\d+ /, "")}`}
            </TooltipContent>
          </Tooltip>
        ))}
        {active != null && (
          <button type="button" className="text-xs underline underline-offset-2 hover:text-(--vm-fg)" onClick={() => onToggle(null)}>
            Show all
          </button>
        )}
      </ToggleGroup>
    </div>
  );
}
