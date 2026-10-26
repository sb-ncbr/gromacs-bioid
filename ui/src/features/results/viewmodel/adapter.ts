/**
 * API → view-model adapter (bioid_ui_handoff/DATA.md).
 *
 * The one module allowed to know both worlds: it consumes the API payload
 * shapes (generated OpenAPI types are structurally assignable to the *View
 * interfaces below) and produces the ViewModel every component reads.
 *
 * Gaps G1–G9 (see ui/BACKEND_GAPS.md) degrade as documented in DATA.md §4:
 * name → first input file; copies hidden; notes without "Affects"; hit
 * names fall back to "DB ID"; CSV hidden until available.
 */
import type {
  DownloadEntry,
  Molecule,
  MoleculeResult,
  TechnicalEntry,
  ViewModel,
  RunStatus,
} from "./types";
import { KIND_LABELS } from "./labels";
import { catalog } from "./warningCatalog";
import {
  baseName,
  clause,
  elapsed,
  evidence,
  formatDb,
  formatInput,
  kindOf,
  stateOf,
  statusOf,
  type HitView,
} from "./derive";
import { steps, type TaskView } from "./steps";
import { notes as groupNotes, unidentifiedNote, type WarningView } from "./notes";

/* ------------------------------------------------------------------ */
/* Structural input views (generated API types are assignable to these) */
/* ------------------------------------------------------------------ */

export interface SummaryView {
  status?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  input_kind?: string | null;
  submitted_at?: string | null;
  /** G1 additive field. */
  run_name?: string | null;
}

export interface ErrorView {
  code?: string;
  message?: string;
  step_id?: string | null;
  critical?: boolean | null;
}

export interface StatusView {
  pipeline?: { status?: string | null } | null;
  tasks?: TaskView[];
  warnings?: WarningView[];
  critical_errors?: ErrorView[];
  /** G2 additive progress block. */
  progress?: { molecules_done?: number | null; molecules_total?: number | null } | null;
}

export interface MetaView {
  type?: string | null;
  atom_count?: number | null;
  residue_count?: number | null;
  residue_names?: string[] | null;
  /** G3 additive fields. */
  copies?: number | null;
  display_name?: string | null;
  chain?: string | null;
}

export interface MoleculesView {
  segments?: string[];
  segment_meta?: Record<string, MetaView | undefined> | null;
}

export interface SignatureView {
  segment?: string;
  generator?: string;
  signature?: unknown;
}

export interface SignaturesView {
  signatures?: SignatureView[];
}

export interface VerificationView {
  segment?: string;
  hits?: HitView[];
}

export interface QueueView {
  state?: string;
  position?: number | null;
  ahead?: number | null;
}

export interface FilesView {
  files?: string[];
}

export interface ApiBundle {
  runId: string;
  summary: SummaryView | null;
  status: StatusView | null;
  molecules: MoleculesView | null;
  signatures: SignaturesView | null;
  verification: VerificationView[] | null;
  queue: QueueView | null;
  files: FilesView | null;
}

export interface AdapterOptions {
  /** ms epoch; inject for deterministic tests. */
  now?: number;
  /** Deployment-config retention (G8-class config; hidden when null). */
  retentionDays?: number | null;
  /** Typical duration text, e.g. "30–120 min"; omitted when null. */
  typical?: string | null;
  /** Flip when backend gap G6 lands. */
  csvAvailable?: boolean;
}

/* ------------------------------------------------------------------ */
/* Small pure helpers                                                   */
/* ------------------------------------------------------------------ */

function runStatus(bundle: ApiBundle): RunStatus {
  if (bundle.queue?.state === "queued") return "queued";
  const s = bundle.summary?.status ?? bundle.status?.pipeline?.status ?? "pending";
  if (s === "success") return "finished";
  if (s === "failed" || s === "error" || s === "cancelled") return "failed";
  return "running";
}

function basename(path: string): string {
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

/** Extract display text from a signature payload of unknown shape. */
function text(sig: unknown, keys: string[]): string | null {
  if (typeof sig === "string") return sig;
  if (typeof sig === "number") return String(sig);
  if (sig && typeof sig === "object") {
    const rec = sig as Record<string, unknown>;
    for (const k of keys) {
      const v = rec[k];
      if (typeof v === "string") return v;
      if (typeof v === "number") return String(v);
    }
  }
  return null;
}

/** Protein sequence: strip FASTA header lines if present. */
function sequence(sig: unknown): string | undefined {
  const raw = text(sig, ["sequence", "fasta", "value", "text"]);
  if (!raw) return undefined;
  return raw
    .split("\n")
    .filter((line) => !line.startsWith(">"))
    .join("")
    .trim() || undefined;
}

function names(sig: unknown): string[] {
  if (Array.isArray(sig)) return sig.map(String);
  const raw = text(sig, ["residues", "names", "value"]);
  return raw ? raw.split(/[,\s]+/).filter(Boolean) : [];
}

/* ------------------------------------------------------------------ */
/* Molecules                                                            */
/* ------------------------------------------------------------------ */

function sorted(hits: HitView[]): HitView[] {
  return [...hits].sort((a, b) => (b.final_confidence ?? -1) - (a.final_confidence ?? -1));
}

function resultOf(hits: HitView[]): {
  result: MoleculeResult;
  matches: Molecule["matches"];
  more: Molecule["more"];
} {
  const verified = sorted(hits.filter((h) => h.is_verified));
  const rejected = hits.filter((h) => !h.is_verified);
  const related = hits.filter(
    (h) => h.equivalence_class_id != null || (h.similarity_score == null && h.skeleton_sim != null),
  );
  const top = verified[0] ?? null;
  const state = stateOf(top, verified.length > 0);
  const exact = state === "exact";
  const best = top
    ? { db: formatDb(top.database), id: top.identifier ?? "", url: top.database_url ?? "" }
    : null;
  return {
    result: {
      state,
      name: top?.name ?? null,
      description: top?.organism ?? null,
      best,
      confidence: exact ? null : (top?.final_confidence ?? null),
    },
    matches: verified.slice(1).map((h) => ({
      db: formatDb(h.database),
      id: h.identifier ?? "",
      url: h.database_url ?? "",
      what: h.name ?? `${formatDb(h.database)} ${h.identifier ?? ""}`,
      evidence: evidence(h),
      confidence: h.final_confidence ?? null,
    })),
    more: { verified: verified.length, related: related.length, rejected: rejected.length },
  };
}

function buildMolecules(bundle: ApiBundle, status: RunStatus, stageSearch = true): Molecule[] {
  const segments = bundle.molecules?.segments ?? [];
  const meta = bundle.molecules?.segment_meta ?? {};
  const searchStage = steps(bundle.status?.tasks ?? [], 0).find((s) => s.key === "search");
  const bySeg = new Map((bundle.verification ?? []).map((v) => [v.segment ?? "", v.hits ?? []]));
  const sigs = new Map<string, SignatureView[]>();
  for (const s of bundle.signatures?.signatures ?? []) {
    const list = sigs.get(s.segment ?? "") ?? [];
    list.push(s);
    sigs.set(s.segment ?? "", list);
  }

  const built = segments.map((id): Molecule => {
    const m = meta[id] ?? {};
    const named = baseName(id);
    // Once verification data is loaded, a segment without an entry means
    // "searched, nothing verified" — not "no data" (feeds not_identified).
    const hits = bySeg.get(id) ?? (bundle.verification != null ? [] : undefined);
    const mine = sigs.get(id) ?? [];
    const find = (gen: string) => mine.find((s) => s.generator === gen)?.signature;
    const { result, matches, more } =
      hits != null
        ? resultOf(hits)
        : { result: null, matches: [], more: { verified: 0, related: 0, rejected: 0 } };
    return {
      id,
      display_name: m.display_name ?? named.name,
      kind: kindOf(m.type),
      chain: m.chain ?? named.chain,
      residue_names: names(find("resname")),
      copies: m.copies ?? 1,
      atoms_per_copy: m.atom_count ?? 0,
      residues_per_copy: m.residue_count ?? null,
      status: hits != null && status === "finished" ? "done" : statusOf(status, searchStage),
      result,
      matches,
      more,
      descriptor: {
        sequence: sequence(find("fasta_map_protein")),
        formula: text(find("molecular_formula"), ["formula", "value"]) ?? undefined,
        smiles: text(find("smiles"), ["smiles", "value"]) ?? undefined,
        inchikey: text(find("inchi_key"), ["inchikey", "inchi_key", "value"]) ?? undefined,
        element: text(find("atom"), ["element", "value"]) ?? undefined,
      },
      note_ids: [],
    };
  });

  // Duplicate labels gain the kind in parens: "SOD (ion)" (DATA.md §2).
  const counts = new Map<string, number>();
  for (const b of built) counts.set(b.display_name, (counts.get(b.display_name) ?? 0) + 1);
  for (const b of built) {
    if ((counts.get(b.display_name) ?? 0) > 1) {
      b.display_name = `${b.display_name} (${KIND_LABELS[b.kind]})`;
    }
  }
  void stageSearch;
  return built;
}

/* ------------------------------------------------------------------ */
/* Run-level pieces                                                     */
/* ------------------------------------------------------------------ */

function errorOf(bundle: ApiBundle, status: RunStatus, shortId: string) {
  if (status !== "failed") return null;
  const errors = bundle.status?.critical_errors ?? [];
  const first = errors.find((e) => e.critical) ?? errors[0];
  const entry = catalog(first?.code ?? "pipeline_execution_failed");
  const fillIn = (t: string) =>
    t.replaceAll("{short_id}", shortId).replaceAll("{step}", "the run");
  return {
    title: fillIn(entry.title),
    body: fillIn(entry.body),
    action: fillIn(entry.action ?? "Rerun."),
    technical: first ? `${first.code ?? "unknown"}: ${first.message ?? ""}` : "",
  };
}

function downloads(csvAvailable: boolean): DownloadEntry[] {
  const json: DownloadEntry = { key: "json", label: "All results (JSON)", primary: !csvAvailable };
  return csvAvailable
    ? [{ key: "csv", label: "Results table (CSV)", primary: true }, json]
    : [json];
}

/** Technical-details fold entries (COPY.md §2.7, in order). */
const TECHNICAL: TechnicalEntry[] = [
  { key: "input", title: "Your files and how they were read", desc: "Input files, loader, strategies" },
  { key: "timings", title: "Step timings", desc: "Start, end and duration of every step" },
  { key: "signatures", title: "Molecule descriptions", desc: "Signatures used for the search" },
  { key: "searches", title: "Database searches", desc: "Every resolver and its raw hits" },
  { key: "candidates", title: "All candidates with scores", desc: "Verified and rejected, with reasons" },
  { key: "messages", title: "All messages with codes", desc: "Raw warnings and errors" },
  { key: "logs", title: "Logs and settings used", desc: "Run configuration and logs" },
];

/* ------------------------------------------------------------------ */
/* The adapter                                                          */
/* ------------------------------------------------------------------ */

export function adapt(bundle: ApiBundle, options: AdapterOptions = {}): ViewModel {
  const now = options.now ?? Date.now();
  const status = runStatus(bundle);
  const shortId = bundle.runId.slice(0, 8);
  const stages = steps(bundle.status?.tasks ?? [], now);
  const molecules = buildMolecules(bundle, status);

  const { notes: catalogNotes, hidden } = groupNotes(bundle.status?.warnings);
  // Derived "not identified" note; only once results exist (SPEC.md §3.3).
  const missed = molecules.filter(
    (m) => m.result && (m.result.state === "not_identified" || m.result.state === "lead"),
  );
  const derived = missed.length ? unidentifiedNote(missed.map((m) => m.display_name), missed.map((m) => m.id)) : null;
  const allNotes = derived ? [derived, ...catalogNotes] : catalogNotes;
  if (derived) {
    for (const m of missed) m.note_ids.push(derived.id);
  }

  const files = bundle.files?.files ?? [];
  const atoms = molecules.reduce((sum, m) => sum + m.atoms_per_copy * m.copies, 0);
  const rawName = bundle.summary?.run_name ?? (files[0] ? basename(files[0]) : null);
  const progressBlock = bundle.status?.progress ?? null;

  return {
    run: {
      id: bundle.runId,
      short_id: shortId,
      name: rawName ?? `Run ${shortId}`,
      status,
      input: {
        format: formatInput(bundle.summary?.input_kind),
        files: files.map(basename),
        atoms,
      },
      submitted_at: bundle.summary?.submitted_at ?? bundle.summary?.started_at ?? "",
      started_at: bundle.summary?.started_at ?? null,
      finished_at: bundle.summary?.finished_at ?? null,
      elapsed_s: elapsed(status, bundle.summary?.started_at, bundle.summary?.finished_at, now),
      retention_days: options.retentionDays ?? null,
    },
    progress: {
      stages,
      molecules_done: progressBlock?.molecules_done ?? null,
      molecules_total: progressBlock?.molecules_total ?? (molecules.length || null),
      typical: options.typical ?? null,
      queue_position: bundle.queue?.ahead ?? bundle.queue?.position ?? null,
    },
    error: errorOf(bundle, status, shortId),
    notes: allNotes,
    hidden_note_count: hidden,
    molecules,
    downloads: downloads(options.csvAvailable ?? false),
    technical: TECHNICAL,
  };
}

export { clause };
