/**
 * View-model contract for the run-results page (bioid_ui_handoff/DATA.md §1).
 *
 * Every component on the redesigned /runs/:id page reads ONLY from these
 * shapes. All API-to-view-model derivation lives in ./adapter.ts, so backend
 * changes stay contained in one module and the page can be tested on the
 * handoff fixtures (./fixtures/).
 */

export type RunStatus = "queued" | "running" | "finished" | "failed";

export type StageKey = "read" | "find" | "describe" | "search" | "check" | "save";
export type StageStatus = "done" | "active" | "waiting" | "failed";

export interface Stage {
  key: StageKey;
  label: string;
  status: StageStatus;
  duration_s: number | null;
}

export type NoteSeverity = "attention" | "info";

export interface Note {
  id: string;
  severity: NoteSeverity;
  code: string;
  title: string;
  body: string;
  action: string | null;
  /** Molecule ids (segment ids). Empty until backend gap G4 lands. */
  affects: string[];
  /** How many raw warnings were merged into this note. */
  raw_count: number;
}

export type MoleculeKind =
  | "protein"
  | "nucleic"
  | "small_molecule"
  | "lipid"
  | "unknown"
  | "ion"
  | "water";

export type MoleculeStatus =
  | "waiting"
  | "searching"
  | "searched"
  | "not_searched"
  | "done";

export type ResultState = "identified" | "lead" | "exact" | "not_identified";

export interface MatchEntry {
  db: string;
  id: string;
  url: string;
  what: string;
  evidence: string;
  confidence: number | null;
}

export interface MoleculeResult {
  state: ResultState;
  name: string | null;
  description: string | null;
  best: { db: string; id: string; url: string } | null;
  /** 0–100; null for exact matches. */
  confidence: number | null;
  /** "Match to your molecule" phrase for the best hit (matches-table top row). */
  evidence?: string | null;
}

export interface MoleculeDescriptor {
  sequence?: string;
  formula?: string;
  smiles?: string;
  inchikey?: string;
  element?: string;
}

export interface RejectedEntry {
  db: string;
  id: string;
  what: string;
  /** Short rewritten clause (COPY.md §4); raw reason stays under Technical details. */
  clause: string;
}

export interface Molecule {
  /** Segment id, e.g. "seg_0_Protein_chain_A" (never displayed). */
  id: string;
  display_name: string;
  kind: MoleculeKind;
  chain: string | null;
  residue_names: string[];
  copies: number;
  atoms_per_copy: number;
  residues_per_copy: number | null;
  status: MoleculeStatus;
  result: MoleculeResult | null;
  matches: MatchEntry[];
  more: { verified: number; related: number; rejected: number };
  /** Rejected candidates with rewritten reasons ("Rejected candidates (N)"). */
  rejected?: RejectedEntry[];
  descriptor: MoleculeDescriptor;
  note_ids: string[];
}

export interface RunError {
  title: string;
  body: string;
  action: string;
  technical: string;
}

export interface DownloadEntry {
  key: "csv" | "json";
  label: string;
  primary: boolean;
}

export interface TechnicalEntry {
  key: string;
  title: string;
  desc: string;
}

export interface ViewModel {
  run: {
    id: string;
    short_id: string;
    name: string;
    status: RunStatus;
    /** The run was cancelled (shown as stopped, not as an error). */
    cancelled: boolean;
    input: { format: string; files: string[]; atoms: number };
    submitted_at: string;
    started_at: string | null;
    finished_at: string | null;
    elapsed_s: number | null;
    retention_days: number | null;
  };
  progress: {
    stages: Stage[];
    /** null → indeterminate bar (backend gap G2). */
    molecules_done: number | null;
    molecules_total: number | null;
    typical: string | null;
    queue_position: number | null;
  };
  error: RunError | null;
  notes: Note[];
  hidden_note_count: number;
  /** File order. */
  molecules: Molecule[];
  downloads: DownloadEntry[];
  technical: TechnicalEntry[];
}
