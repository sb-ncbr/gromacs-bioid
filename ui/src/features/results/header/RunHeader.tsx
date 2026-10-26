/**
 * RunHeader (SPEC.md §2 actions table, §3.1): status chip, H1, meta line
 * with short id + [Copy link], state-dependent actions. Cancel asks for
 * confirmation in-page. All run-level; downloads never per molecule.
 */
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
  Badge,
  Button,
  cn,
} from "@e-infra/design-system";
import { Check, CircleX, Clock, Download, FileText, Link2, Loader2, SquarePen } from "lucide-react";
import type { RunStatus, ViewModel } from "../viewmodel";
import { CANCEL_CONFIRM, headerActions, metaLine, pageName } from "./headerModel";

const CHIP: Record<RunStatus, { label: string; icon: typeof Clock; cls: string }> = {
  queued: { label: "Queued", icon: Clock, cls: "border-(--vm-line) text-(--vm-muted)" },
  running: { label: "Running", icon: Loader2, cls: "border-(--vm-info) text-(--vm-info)" },
  finished: { label: "Finished", icon: Check, cls: "border-(--vm-high) text-(--vm-high)" },
  failed: { label: "Failed", icon: CircleX, cls: "border-(--vm-none) text-(--vm-none)" },
};

export interface RunHeaderProps {
  run: ViewModel["run"];
  runStatus: RunStatus;
  downloads: ViewModel["downloads"];
  onCopyLink: () => void;
  onCancel: () => void;
  onRerun: () => void;
  onCite: () => void;
  onDownload: (key: "csv" | "json") => void;
  onReport: () => void;
}

function copyLinkFallback() {
  void navigator.clipboard?.writeText(window.location.href);
}

export function RunHeader({ run, runStatus, downloads, onCopyLink, onCancel, onRerun, onCite, onDownload, onReport }: RunHeaderProps) {
  const chip = CHIP[runStatus];
  const ChipIcon = chip.icon;
  const actions = headerActions(runStatus, downloads);

  return (
    <header className="mb-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <h1 className="truncate text-2xl font-bold text-(--vm-fg)">{pageName(run)}</h1>
          <Badge variant="outline" className={cn("gap-1.5 px-2.5 py-1 text-[13px]", chip.cls)}>
            <ChipIcon size={14} aria-hidden className={runStatus === "running" ? "motion-safe:animate-spin" : undefined} />
            {chip.label}
          </Badge>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {actions.map((a) => {
            if (a.kind === "cancel") {
              return (
                <AlertDialog key="cancel">
                  <AlertDialogTrigger asChild>
                    <Button variant="outline" size="sm">
                      {a.label}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>{CANCEL_CONFIRM.title}</AlertDialogTitle>
                      <AlertDialogDescription>{CANCEL_CONFIRM.body}</AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>{CANCEL_CONFIRM.dismiss}</AlertDialogCancel>
                      <AlertDialogAction
                        className="bg-(--vm-none) text-(--vm-none-fg,#fff) hover:bg-(--vm-none)/90"
                        onClick={onCancel}
                      >
                        {CANCEL_CONFIRM.confirm}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              );
            }
            if (a.kind === "download") {
              return (
                <Button key={a.key} variant={a.primary ? "default" : "outline"} size="sm" onClick={() => onDownload(a.key)}>
                  <Download size={14} className="mr-1" aria-hidden />
                  {a.label}
                </Button>
              );
            }
            if (a.kind === "cite") {
              return (
                <Button key="cite" variant="outline" size="sm" onClick={onCite}>
                  <FileText size={14} className="mr-1" aria-hidden />
                  {a.label}
                </Button>
              );
            }
            if (a.kind === "report") {
              return (
                <Button key="report" variant="outline" size="sm" onClick={onReport}>
                  <SquarePen size={14} className="mr-1" aria-hidden />
                  {a.label}
                </Button>
              );
            }
            return (
              <Button key="rerun" variant={a.primary ? "default" : "outline"} size="sm" onClick={onRerun}>
                {a.label}
              </Button>
            );
          })}
        </div>
      </div>
      <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-(--vm-muted)">
        <span>{metaLine(run)}</span>
        <button
          type="button"
          onClick={() => (onCopyLink ?? copyLinkFallback)()}
          className="inline-flex items-center gap-1 text-(--vm-accent) underline-offset-2 hover:underline"
        >
          <Link2 size={13} aria-hidden /> Copy link
        </button>
      </p>
    </header>
  );
}

export default RunHeader;
