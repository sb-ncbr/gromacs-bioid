/**
 * Answer header — the top of the stage card (SPEC.md §3.5a).
 * Eyebrow · identified-name title · best-match/same-as line · confidence badge.
 */
import { Badge, cn } from "@e-infra/design-system";
import { ExternalLink } from "lucide-react";
import type { Molecule, RunStatus } from "../viewmodel";
import { CONFIDENCE_ICONS, CONFIDENCE_COLOR } from "../list";
import { badgeOf, bestLine, eyebrow, headline, sameAs, type Badge as BadgeModel } from "./stageModel";

export interface AnswerHeaderProps {
  molecule: Molecule;
  molecules: Molecule[];
  runStatus: RunStatus;
  onSelect: (id: string) => void;
}

const BADGE_CLASSES: Record<string, string> = {
  high: "border-(--vm-high) text-(--vm-high)",
  medium: "border-(--vm-medium) text-(--vm-medium)",
  low: "border-(--vm-low) text-(--vm-low)",
  exact: "border-(--vm-high) text-(--vm-high)",
  none: "border-(--vm-none) text-(--vm-none)",
  status: "border-(--vm-info) text-(--vm-info)",
};

function ConfBadge({ badge }: { badge: BadgeModel }) {
  const Icon = CONFIDENCE_ICONS[badge.kind === "status" ? "searching" : badge.kind];
  const colorClass =
    badge.kind === "status" ? "text-(--vm-info)" : CONFIDENCE_COLOR[badge.kind as keyof typeof CONFIDENCE_COLOR];
  return (
    <Badge variant="outline" className={cn("gap-1.5 px-3 py-1.5 text-sm whitespace-nowrap", BADGE_CLASSES[badge.kind])}>
      <Icon size={16} className={cn(colorClass, badge.kind === "status" && "motion-safe:animate-spin")} aria-hidden />
      {badge.text}
    </Badge>
  );
}

export function AnswerHeader({ molecule, molecules, runStatus, onSelect }: AnswerHeaderProps) {
  const resolved = runStatus === "finished";
  const title = headline(molecule, resolved);
  const best = bestLine(molecule, resolved);
  const siblings = resolved ? sameAs(molecules, molecule.id) : [];
  const badge = badgeOf(molecule, resolved, molecule.status === "searching" ? "Searching databases…" : undefined);
  const shown = siblings.slice(0, 5);
  const extra = siblings.length - shown.length;

  return (
    <div className="flex items-start justify-between gap-4 px-5 pt-5 pb-4">
      <div className="min-w-0">
        <p className="text-xs uppercase tracking-wide text-(--vm-muted)">{eyebrow(molecule)}</p>
        <h2 className="mt-1 text-[22px] font-bold leading-snug text-(--vm-fg)">
          {title.title}
          {title.sub && <span className="ml-2 font-normal italic text-(--vm-fg-2) text-base">{title.sub}</span>}
        </h2>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          {best &&
            (best.url ? (
              <a
                href={best.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-(--vm-accent) underline-offset-2 hover:underline"
              >
                Best match {best.db} {best.id}
                <ExternalLink size={13} aria-hidden />
                <span className="sr-only">(opens in a new tab)</span>
              </a>
            ) : (
              <span className="text-(--vm-fg-2)">
                Best match {best.db} {best.id}
              </span>
            ))}
          {siblings.length > 0 && (
            <span className="text-(--vm-muted)">
              · Same as{" "}
              {shown.map((s, i) => (
                <span key={s.id}>
                  {i > 0 && ", "}
                  <button
                    type="button"
                    onClick={() => onSelect(s.id)}
                    className="text-(--vm-accent) underline-offset-2 hover:underline"
                  >
                    {s.label}
                  </button>
                </span>
              ))}
              {extra > 0 && ` and ${extra} more`}
            </span>
          )}
        </div>
      </div>
      <ConfBadge badge={badge} />
    </div>
  );
}
