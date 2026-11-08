/**
 * ErrorBanner (SPEC.md §3.2): role="alert", error colour role; title +
 * one-sentence body + What-to-do; the raw exception lives behind an
 * in-banner Technical-detail fold. Rerun and the bug report are the run
 * header's actions, so the banner does not repeat them. A cancelled run
 * gets the same banner in neutral colours (stopped on request, not an error).
 */
import { Collapsible, CollapsibleContent, CollapsibleTrigger, cn } from "@e-infra/design-system";
import { ChevronDown } from "lucide-react";
import type { RunError, ViewModel } from "../viewmodel";

export interface ErrorBannerProps {
  run: ViewModel["run"];
  error: RunError;
}

export function ErrorBanner({ run, error }: ErrorBannerProps) {
  const cancelled = run.cancelled;
  return (
    <div
      role={cancelled ? "status" : "alert"}
      className={cn(
        "mb-4 rounded-lg border px-4 py-3",
        cancelled ? "border-(--vm-line) bg-(--vm-surface-2)" : "border-(--vm-error-line) bg-(--vm-error-bg)",
      )}
    >
      <p className={cn("text-sm font-semibold", cancelled ? "text-(--vm-fg)" : "text-(--vm-error)")}>{error.title}</p>
      <p className="mt-0.5 text-sm text-(--vm-fg-2)">{error.body}</p>
      {error.action && <p className="mt-1 text-sm font-medium text-(--vm-fg)">What to do: {error.action}</p>}
      {error.technical && (
        <Collapsible className="mt-2">
          <CollapsibleTrigger className="inline-flex min-h-6 items-center gap-1 text-sm text-(--vm-muted) hover:text-(--vm-fg) [&[data-state=open]>svg]:rotate-180">
            Technical detail <ChevronDown size={14} aria-hidden className="transition-transform" />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <pre className="mt-1 max-h-48 overflow-auto rounded-md bg-(--vm-surface-2) p-3 font-mono text-xs whitespace-pre-wrap break-all text-(--vm-fg-2)">
              {error.technical}
            </pre>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}

export default ErrorBanner;
