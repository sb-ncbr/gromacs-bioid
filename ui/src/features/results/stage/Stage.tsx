/**
 * Stage — one card for the selected molecule (SPEC.md §3.5):
 * answer header → Mol* canvas slot → tabs. Selection is the parent's;
 * the last-used tab is remembered across selections when still valid.
 */
import { useState, type ReactNode } from "react";
import { Card } from "@e-infra/design-system";
import type { Molecule, Note, RunStatus } from "../viewmodel";
import { AnswerHeader } from "./AnswerHeader";
import { StageTabs, tabsFor, type StageTab } from "./StageTabs";

export interface StageProps {
  molecule: Molecule;
  molecules: Molecule[];
  notes: Note[];
  runStatus: RunStatus;
  onSelect: (id: string) => void;
  /** The Mol* canvas (StageCanvas), injected so layout/test stay light. */
  canvas: ReactNode;
}

export function Stage({ molecule: m, molecules, notes, runStatus, onSelect, canvas }: StageProps) {
  const [tab, setTab] = useState<StageTab>("matches");

  // Remember the tab across selections when the new molecule has it;
  // otherwise fall back to the first (derived during render, no effect).
  const validTab: StageTab = tabsFor(m).some((t) => t.key === tab) ? tab : "matches";

  return (
    <section aria-labelledby="stage-title" className="min-w-0">
      <Card className="overflow-hidden">
        <h2 id="stage-title" className="sr-only">
          {m.display_name}
        </h2>
        <AnswerHeader molecule={m} molecules={molecules} runStatus={runStatus} onSelect={onSelect} />
        <div className="px-5 pb-3">{canvas}</div>
        <div className="pb-4">
          <StageTabs molecule={m} notes={notes} runStatus={runStatus} tab={validTab} onTab={setTab} />
        </div>
      </Card>
    </section>
  );
}

export default Stage;
