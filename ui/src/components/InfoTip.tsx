/**
 * Info button with a short explanation and a link to the documentation
 * (2026-11-27 accessibility round). A real button, so it is reachable by
 * keyboard and touch (a `title` tooltip is neither) and announced by screen
 * readers as "About <topic>"; Radix Popover closes on Escape and returns
 * focus to the button. Texts live in lib/help.ts.
 */
import { Popover, PopoverContent, PopoverTrigger, cn } from "@e-infra/design-system";
import { BookOpen, Info } from "lucide-react";
import { HELP, docsHref, type HelpEntry, type HelpKey } from "../lib/help";

export interface InfoTipProps {
  /** A catalogue entry (lib/help.ts) ... */
  topic?: HelpKey;
  /** ... or an entry of its own (configuration field help). */
  entry?: HelpEntry;
  side?: "top" | "right" | "bottom" | "left";
  className?: string;
}

export function InfoTip({ topic, entry, side = "top", className }: InfoTipProps) {
  const h: HelpEntry | undefined = entry ?? (topic ? HELP[topic] : undefined);
  if (!h) return null;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`About ${h.title}`}
          // stop a click from also reaching a sortable header or row handler
          onClick={(e) => e.stopPropagation()}
          className={cn(
            "inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full align-middle",
            "text-(--vm-muted) hover:text-(--vm-fg) focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-(--vm-accent)",
            className,
          )}
        >
          <Info size={14} aria-hidden />
        </button>
      </PopoverTrigger>
      <PopoverContent side={side} className="w-80 max-w-[calc(100vw-2rem)] text-sm normal-case tracking-normal">
        <p className="font-semibold text-(--vm-fg)">{h.title}</p>
        <p className="mt-1 font-normal leading-relaxed text-(--vm-fg-2)">{h.body}</p>
        {h.docs && (
          <a
            href={docsHref(h.docs)}
            target="_blank"
            rel="noreferrer"
            className="mt-2 inline-flex items-center gap-1 font-normal text-(--vm-accent) underline-offset-2 hover:underline"
          >
            <BookOpen size={13} aria-hidden /> Read more in the documentation
            <span className="sr-only">(opens in a new tab)</span>
          </a>
        )}
      </PopoverContent>
    </Popover>
  );
}

/** A column header label with its info button. */
export function HeadLabel({ children, topic }: { children: React.ReactNode; topic: HelpKey }) {
  return (
    <span className="inline-flex items-center gap-1">
      {children}
      <InfoTip topic={topic} side="bottom" />
    </span>
  );
}
