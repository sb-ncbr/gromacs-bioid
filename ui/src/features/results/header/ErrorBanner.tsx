/**
 * ErrorBanner (SPEC.md §3.2): role="alert", error colour role; title +
 * one-sentence body + What-to-do; [Rerun] [Copy details for a bug report];
 * the raw exception lives behind an in-banner Technical-detail fold.
 */
import { Button, Collapsible, CollapsibleContent, CollapsibleTrigger } from "@e-infra/design-system";
import { ChevronDown, Copy, RotateCw } from "lucide-react";
import type { RunError, ViewModel } from "../viewmodel";
import { bugReport } from "./headerModel";

export interface ErrorBannerProps {
  run: ViewModel["run"];
  error: RunError;
  onRerun: () => void;
}

export function ErrorBanner({ run, error, onRerun }: ErrorBannerProps) {
  return (
    <div role="alert" className="mb-4 rounded-lg border border-(--vm-error-line) bg-(--vm-error-bg) px-4 py-3">
      <p className="text-sm font-semibold text-(--vm-error)">{error.title}</p>
      <p className="mt-0.5 text-sm text-(--vm-fg-2)">{error.body}</p>
      {error.action && <p className="mt-1 text-sm font-medium text-(--vm-fg)">What to do: {error.action}</p>}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={onRerun}>
          <RotateCw size={14} className="mr-1" aria-hidden /> Rerun
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            void navigator.clipboard?.writeText(bugReport(run, error)).then(() => {
              import("sonner").then(({ toast }) => toast.success("Details copied")).catch(() => {});
            });
          }}
        >
          <Copy size={14} className="mr-1" aria-hidden /> Copy details for a bug report
        </Button>
        <Collapsible className="basis-full">
          <CollapsibleTrigger className="inline-flex items-center gap-1 text-sm text-(--vm-muted) hover:text-(--vm-fg) [&[data-state=open]>svg]:rotate-180">
            Technical detail <ChevronDown size={14} aria-hidden className="transition-transform" />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <pre className="mt-1 max-h-48 overflow-auto rounded-md bg-(--vm-surface-2) p-3 font-mono text-xs whitespace-pre-wrap break-all text-(--vm-fg-2)">
              {error.technical}
            </pre>
          </CollapsibleContent>
        </Collapsible>
      </div>
    </div>
  );
}

export default ErrorBanner;
