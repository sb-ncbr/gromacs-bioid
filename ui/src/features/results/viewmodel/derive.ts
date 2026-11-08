/**
 * Pure derivation helpers (bioid_ui_handoff/DATA.md §2, SPEC.md §4).
 * No API knowledge beyond the hit/segment shapes — adapter.ts wires the rest.
 */
import type { MoleculeKind, MoleculeStatus, ResultState, RunStatus, Stage } from "./types";
import { DB_LABELS, FORMAT_LABELS, KIND_LABELS, KIND_MAP } from "./labels";

/**
 * Local, permissive hit shape: the generated VerifiedHitItem plus additive
 * fields the UI wants (G5). Structural typing keeps the generated baseline
 * assignable while letting newer API payloads carry names.
 */
export interface HitView {
  identifier?: string | null;
  ident_type?: string | null;
  database?: string | null;
  similarity_score?: number | null;
  skeleton_sim?: number | null;
  final_confidence?: number | null;
  is_verified?: boolean;
  rejection_reason?: string | null;
  database_url?: string | null;
  ground_truth_override?: string | null;
  equivalence_class_id?: string | null;
  /** G5 additive fields (not yet in the generated baseline). */
  name?: string | null;
  organism?: string | null;
}

/** Segment id → source string: strip `seg_N_` prefix and `__vN` suffix. */
export function stripSeg(id: string): string {
  return id.replace(/^seg_\d+_/, "").replace(/__v\d+$/, "");
}

/** Chain letter from a stripped segment source ("Protein_chain_A" → "A"). */
export function chainOf(source: string): string | null {
  const m = /(?:^|_)chain_([A-Za-z0-9]+)$/.exec(source);
  return m ? m[1] : null;
}

/**
 * Base display name for one segment (before duplicate disambiguation):
 * chains → "Chain X"; otherwise the residue/source name (DATA.md §2).
 */
export function baseName(id: string): { name: string; chain: string | null } {
  const source = stripSeg(id);
  const chain = chainOf(source);
  return chain ? { name: `Chain ${chain}`, chain } : { name: source, chain: null };
}

/**
 * Readable label for API display names that are bare chain ids: PDB input
 * segments are named "A" (chain A) or "A_2" (chain A, fragment 2). Polymers
 * read "Chain A"; other fragments name their residue: "NAG (chain E)".
 * Anything else is already a name and passes through.
 */
export function chainLabel(name: string, kind: MoleculeKind, residueNames: string[]): string {
  const m = /^([A-Za-z0-9])(_\d+)?$/.exec(name);
  if (!m) return name;
  const chain = m[1];
  if (kind === "protein" || kind === "nucleic") return `Chain ${chain}`;
  const res = residueNames[0];
  if (!m[2] && (!res || res === name)) return name; // a one-letter residue name, e.g. ion "K"
  const what = res ?? KIND_LABELS[kind].charAt(0).toUpperCase() + KIND_LABELS[kind].slice(1);
  return `${what} (chain ${chain})`;
}

/** Loader type string → view-model kind (unknown/lipid quirk documented in G3). */
export function kindOf(type: string | null | undefined): MoleculeKind {
  return (type && KIND_MAP[type]) || "unknown";
}

/** Database id → display label; falls back to the raw id, title-cased. */
export function formatDb(db: string | null | undefined): string {
  if (!db) return "Database";
  return DB_LABELS[db] ?? db.charAt(0).toUpperCase() + db.slice(1).replace(/_/g, " ");
}

/** Input-format display label. */
export function formatInput(inputKind: string | null | undefined): string {
  if (!inputKind) return "Unknown";
  return FORMAT_LABELS[inputKind] ?? inputKind.toUpperCase();
}

/** Elapsed seconds for the status line (SPEC.md/COPY.md duration rules apply at render time). */
export function elapsed(
  status: RunStatus,
  startedAt: string | null | undefined,
  finishedAt: string | null | undefined,
  now: number,
): number | null {
  if (!startedAt) return null;
  const start = Date.parse(startedAt);
  if (Number.isNaN(start)) return null;
  if (status === "finished" || status === "failed") {
    if (!finishedAt) return null;
    const end = Date.parse(finishedAt);
    if (Number.isNaN(end) || end < start) return null;
    return Math.round((end - start) / 1000);
  }
  if (status === "queued") return null;
  return Math.max(0, Math.round((now - start) / 1000));
}

/** Confidence thresholds (SPEC.md §4 — do not invent new ones). */
export const HIGH_MIN = 80;
export const MEDIUM_MIN = 50;

export function confLabel(confidence: number): "high" | "medium" | "low" {
  if (confidence >= HIGH_MIN) return "high";
  if (confidence >= MEDIUM_MIN) return "medium";
  return "low";
}

/** Result state for the top verified hit (DATA.md §2 result.state). */
export function stateOf(top: HitView | null, hasVerified: boolean): ResultState {
  if (!hasVerified || !top) return "not_identified";
  if (top.ground_truth_override || top.database === "element") return "exact";
  const conf = top.final_confidence;
  if (conf != null && conf < MEDIUM_MIN) return "lead";
  return "identified";
}

const SEQUENCE_DBS = new Set(["pdb", "pdb_id", "uniprot", "uniprot_id", "alphafold"]);
const CHEMICAL_DBS = new Set(["pubchem", "pubchem_cid", "chembl", "chebi"]);

/** Percent helper: similarity scores are fractions (0–1) or percents. */
function pct(value: number | null | undefined): number | null {
  if (value == null) return null;
  const p = value <= 1 ? value * 100 : value;
  return Math.round(p * 10) / 10;
}

function fmtPct(p: number): string {
  return Number.isInteger(p) ? String(p) : p.toFixed(1);
}

/** "Match to your molecule" evidence phrase (COPY.md §2.4). */
export function evidence(hit: HitView): string {
  const db = (hit.database ?? "").toLowerCase();
  if (db === "element") return "same element";
  if (db === "foldseek" || db === "alphafind") return "same structure (stereo not compared)";
  if (db === "pdb" || db === "pdb_id" || db === "uniprot" || db === "uniprot_id" || db === "alphafold") {
    const p = pct(hit.similarity_score);
    if (p != null) return `${fmtPct(p)}% sequence identity`;
    return "matched by sequence";
  }
  if (CHEMICAL_DBS.has(db)) {
    const p = pct(hit.similarity_score);
    if (p != null && p >= 99) return "same structure";
    const s = pct(hit.skeleton_sim);
    if (s != null) return `similar skeleton (${fmtPct(s)}%)`;
    if (p != null) return `similar skeleton (${fmtPct(p)}%)`;
  }
  if (SEQUENCE_DBS.has(db)) return "matched by sequence";
  if (CHEMICAL_DBS.has(db)) return "matched by structure";
  return "database match";
}

/** Rejection reason → short user clause (COPY.md §4). */
export function clause(reason: string | null | undefined): string {
  if (!reason) return "did not pass verification";
  const r = reason.toLowerCase();
  const ident = /identity[^\d]*(\d+(?:\.\d+)?)/.exec(r);
  if (ident) return `sequence identity below ${ident[1]}%`;
  if (/identity/.test(r)) return "sequence identity too low";
  if (/struct/.test(r)) return "structure does not match";
  if (/formula/.test(r)) return "different chemical formula";
  if (/element/.test(r)) return "different element";
  if (/check|verify|fail/.test(r)) return "could not be checked";
  return "did not pass verification";
}

/**
 * Molecule status while running without per-segment progress (G2 fallback,
 * DATA.md §2): waiting before the search step, searching while it runs,
 * searched once it is done; failed runs split searched/not_searched.
 */
export function statusOf(
  runStatus: RunStatus,
  searchStage: Stage | undefined,
): MoleculeStatus {
  if (runStatus === "finished") return "done";
  if (runStatus === "queued") return "waiting";
  const search = searchStage?.status ?? "waiting";
  if (runStatus === "failed") return search === "done" ? "searched" : "not_searched";
  if (search === "done") return "searched";
  if (search === "active") return "searching";
  return "waiting";
}
