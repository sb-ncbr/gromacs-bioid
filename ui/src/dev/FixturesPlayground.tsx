import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, Button } from "@e-infra/design-system";
import TaskBar, { type TaskInfo } from "../features/results/TaskBar";
import MoleculeSelector from "../features/results/MoleculeSelector";
import ResultsPanel from "../features/results/ResultsPanel";
import SignatureDialog from "../features/results/SignatureDialog";
import {
  buildDownloadBlob,
  downloadBlob,
  exportFilename,
  hitsToJson,
  hitsToTsv,
  type VerifiedHit,
} from "../features/results/utils";

import a524Raw from "./fixtures/a524e039.json";
import failedRaw from "./fixtures/4964c437.json";

/* ------------------------------------------------------------------ */
/* Local fixture copies (source: .tmp/tasks/ui-rework/fixtures/)       */
/* ------------------------------------------------------------------ */

const a524 = a524Raw as {
  status: {
    run_id: string;
    pipeline: { status: string; input_kind?: string | null };
    tasks: TaskInfo[];
  };
  molecules: {
    segments?: string[];
    segment_meta?: Record<string, { type?: string; atom_count?: number; residue_count?: number }> | null;
  };
  verification_A: { run_id: string; segment: string; hits?: VerifiedHit[] | null };
  identifiers: {
    run_id: string;
    segment: string;
    hits?: unknown[] | null;
    failed_resolvers?: { resolver_name: string; generator?: string | null; message: string }[] | null;
    attempted_resolvers?: string[] | null;
  };
};

const failed = failedRaw as {
  status: {
    run_id: string;
    pipeline: { status: string; input_kind?: string | null };
    tasks: TaskInfo[];
    warnings?: { code: string; message: string }[];
    critical_errors?: { code: string; message: string; critical: boolean }[];
  };
};

/* Synthetic sample — dev-harness only, to exercise the verification table. */
const SYNTHETIC_HITS: VerifiedHit[] = [
  {
    identifier: "1ABC",
    ident_type: "PDB_ID",
    database: "pdb",
    resolver_score: 100,
    similarity_score: 97.8,
    annotation_quality_score: 100,
    final_confidence: 98.2,
    is_verified: true,
    rejection_reason: null,
    supporting_evidence_count: 3,
    // Note: carries a stale _CHAIN suffix — resolveHitUrl strips it defensively.
    database_url: "https://www.rcsb.org/structure/1ABC_A",
  },
  {
    identifier: "CHEMBL4303682",
    ident_type: "CHEMBL_ID",
    database: "chembl",
    resolver_score: 100,
    similarity_score: 94.11,
    annotation_quality_score: 85,
    final_confidence: 94.87,
    is_verified: true,
    rejection_reason: null,
    supporting_evidence_count: 1,
    database_url: "https://www.ebi.ac.uk/chembl/explore/compound/CHEMBL4303682",
  },
  {
    identifier: "P000000000",
    ident_type: "UNIPROT_ID",
    database: "uniprot",
    resolver_score: 60,
    similarity_score: 41.2,
    annotation_quality_score: 55,
    final_confidence: 44.7,
    is_verified: false,
    rejection_reason: "similarity below threshold (0.41 < 0.50)",
    supporting_evidence_count: 0,
    database_url: null,
  },
];

const DEMO_SIGNATURE = [
  "HEADER    DEMO SIGNATURE (DEVELOPMENT HARNESS PREVIEW)         01-OCT-26",
  "TITLE     SYNTHETIC PREVIEW DATA - NOT FROM A REAL RUN",
  "COMPND    COMPONENT: SEGMENT A (PROTEIN)  ATOMS: 1676",
  "REMARK   1 This sample exists so the SignatureDialog mono preview,",
  "REMARK   2 copy and download controls can be visually verified.",
].join("\n");

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

const FixturesPlayground: React.FC = () => {
  const [selectedSegment, setSelectedSegment] = useState<string>("A");
  const [lastGroupClick, setLastGroupClick] = useState<string | null>(null);
  const [showIdentifiersNote, setShowIdentifiersNote] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);

  const segments: string[] = a524.molecules.segments ?? [];
  const segmentMeta = a524.molecules.segment_meta ?? {};

  // Segment A carries the real degraded-resolver fixture; others have no
  // verification sample in this harness, so they show the plain empty state.
  const verificationFor = (seg: string) =>
    seg === "A" ? a524.verification_A : { segment: seg, hits: [] };
  const identifiersFor = (seg: string) => (seg === "A" ? a524.identifiers : undefined);
  const moleculeFor = (seg: string) => {
    if (seg === "SYSTEM") return null;
    const m = segmentMeta[seg];
    return m ? { type: m.type, atom_count: m.atom_count, residue_count: m.residue_count } : null;
  };

  const handleExport = (fmt: "tsv" | "json") => {
    const content = fmt === "tsv" ? hitsToTsv(SYNTHETIC_HITS) : hitsToJson(SYNTHETIC_HITS);
    const mime = fmt === "tsv" ? "text/tab-separated-values" : "application/json";
    downloadBlob(buildDownloadBlob(content, mime), exportFilename("segment_X_demo", fmt));
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Results UI — Fixture Playground (dev only)</h1>
        <p className="text-sm text-gray-500">
          Renders the results-domain components from local fixture copies. No backend calls.
        </p>
      </div>

      {/* ---------------- Run a524e039 (success, 4 segments) ---------------- */}
      <Card>
        <CardHeader>
          <CardTitle>Run a524e039 (success, pdb, 4 segments)</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <div>
            <h2 className="mb-2 text-sm font-semibold text-gray-600">TaskBar</h2>
            <TaskBar tasks={a524.status.tasks} onGroupClick={setLastGroupClick} />
            {lastGroupClick && (
              <p className="mt-2 text-xs text-gray-500">
                Last group click: <code>{lastGroupClick}</code> → parent would jump to tab/anchor{" "}
                <code>#warn-{lastGroupClick}</code>
              </p>
            )}
          </div>

          <div className="grid gap-6 md:grid-cols-[16rem_1fr]">
            <div>
              <h2 className="mb-2 text-sm font-semibold text-gray-600">MoleculeSelector</h2>
              <MoleculeSelector
                segments={segments}
                segmentMeta={segmentMeta}
                selected={selectedSegment}
                onSelect={setSelectedSegment}
              />
            </div>
            <div>
              <h2 className="mb-2 text-sm font-semibold text-gray-600">
                ResultsPanel — segment {selectedSegment}
              </h2>
              <ResultsPanel
                segment={selectedSegment}
                molecule={moleculeFor(selectedSegment)}
                verification={verificationFor(selectedSegment)}
                identifiers={identifiersFor(selectedSegment)}
                onJumpToIdentifiers={() => setShowIdentifiersNote(true)}
              />
              {showIdentifiersNote && selectedSegment === "A" && (
                <p className="mt-2 text-xs text-gray-500">
                  (Demo) Identifiers tab would now open, listing the 32 failed resolvers from the
                  fixture.
                </p>
              )}
            </div>
          </div>

          <div>
            <h2 className="mb-2 text-sm font-semibold text-gray-600">SignatureDialog</h2>
            <Button size="sm" variant="outline" onClick={() => setDialogOpen(true)}>
              Open signature dialog (pdb_protein, segment A)
            </Button>
            <SignatureDialog
              open={dialogOpen}
              onOpenChange={setDialogOpen}
              generator="pdb_protein"
              signature={DEMO_SIGNATURE}
              segment="A"
            />
          </div>

          <div>
            <h2 className="mb-2 text-sm font-semibold text-gray-600">
              Verification table (synthetic sample data, dev harness only)
            </h2>
            <ResultsPanel
              segment="X"
              molecule={{ type: "small_molecule", atom_count: 73, residue_count: 1 }}
              verification={{ hits: SYNTHETIC_HITS }}
              onExport={handleExport}
            />
          </div>
        </CardContent>
      </Card>

      {/* ---------------- Run 4964c437 (failed) ---------------- */}
      <Card>
        <CardHeader>
          <CardTitle>Run 4964c437 (failed, gromacs)</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <h2 className="text-sm font-semibold text-gray-600">TaskBar (failed run)</h2>
          <TaskBar tasks={failed.status.tasks} onGroupClick={setLastGroupClick} />
          <div className="text-xs text-gray-500">
            <p>Pipeline status: <code>{failed.status.pipeline.status}</code></p>
            {failed.status.critical_errors?.map((e, i) => (
              <p key={i}>
                Critical error recorded: <code>{e.code}</code>
              </p>
            ))}
            <p className="mt-1">
              Per the fixture, the failed stage is <strong>Identify molecules</strong> (shown red);
              Verify/Export never ran (skipped, gray).
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default FixturesPlayground;
