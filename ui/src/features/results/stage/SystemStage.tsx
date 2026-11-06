/**
 * SystemStage — the whole simulated system at once (selection
 * SYSTEM_SELECTION): composition, identification overview and the Mol*
 * canvas with every molecule coloured by confidence. Restores the legacy
 * "Whole system" selector entry the redesign had dropped.
 */
import type { ReactNode } from "react";
import { Card } from "@e-infra/design-system";
import type { Molecule, RunStatus } from "../viewmodel";
import { KIND_LABELS } from "../viewmodel";
import { counts } from "../list/moleculeList";

/** Selection id for the whole system (never a real segment id: MDposit
 * runs have a segment literally named "SYSTEM"). */
export const SYSTEM_SELECTION = "__system__";

export interface SystemStageProps {
  molecules: Molecule[];
  runStatus: RunStatus;
  canvas: ReactNode;
}

function plural(label: string, n: number): string {
  if (n === 1) return `1 ${label}`;
  if (label === "water") return `${n.toLocaleString()} waters`;
  return `${n.toLocaleString()} ${label}s`;
}

/** "1 protein · 1 small molecule · 62 waters" — copies, by kind. */
export function compositionLine(molecules: Molecule[]): string {
  const byKind = new Map<string, number>();
  for (const m of molecules) byKind.set(m.kind, (byKind.get(m.kind) ?? 0) + m.copies);
  return [...byKind.entries()]
    .map(([kind, n]) => plural(KIND_LABELS[kind as Molecule["kind"]] ?? kind, n))
    .join(" · ");
}

export function SystemStage({ molecules, runStatus, canvas }: SystemStageProps) {
  const atoms = molecules.reduce((s, m) => s + m.atoms_per_copy * m.copies, 0);
  const c = counts(molecules, runStatus);
  const finished = runStatus === "finished";
  const identified = (c.high ?? 0) + (c.medium ?? 0) + (c.low ?? 0);
  return (
    <section aria-labelledby="stage-title" className="min-w-0">
      <Card className="overflow-hidden">
        <div className="px-5 pb-3 pt-5">
          <p className="text-[11.5px] font-bold uppercase tracking-wider text-(--vm-muted)">
            Whole system · {molecules.length.toLocaleString()} molecules · {atoms.toLocaleString()} atoms
          </p>
          <h2 id="stage-title" className="mt-1 text-xl font-bold text-(--vm-fg)">
            Whole system
          </h2>
          <p className="mt-1 text-sm text-(--vm-fg-2)">{compositionLine(molecules)}</p>
          {finished && (
            <p className="mt-1 text-sm text-(--vm-muted)">
              {identified} of {molecules.length} molecules identified. Colours show confidence; click a molecule in
              the viewer or pick it in the list to see its matches.
            </p>
          )}
        </div>
        <div className="px-5 pb-5">{canvas}</div>
      </Card>
    </section>
  );
}

export default SystemStage;
