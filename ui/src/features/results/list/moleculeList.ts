/**
 * Molecule list model (SPEC.md §3.4) — pure logic: distribution counting,
 * filter/search, kind grouping, identification grouping, default selection.
 * The component stays a thin renderer over these functions.
 */
import type { Molecule, MoleculeKind, RunStatus } from "../viewmodel";
import { confLabel, KIND_GROUP_LABELS } from "../viewmodel";
import type { IconKey } from "./icons";

/* ------------------------------------------------------------------ */
/* Bucketing (distribution bar = filter)                                */
/* ------------------------------------------------------------------ */

export type DoneBucket = "high" | "medium" | "low" | "none";
export type LiveBucket = "searched" | "searching" | "waiting" | "not_searched";
export type Bucket = DoneBucket | LiveBucket;

export const DONE_BUCKETS: DoneBucket[] = ["high", "medium", "low", "none"];
export const LIVE_BUCKETS: LiveBucket[] = ["searched", "searching", "waiting", "not_searched"];

/**
 * The filter bucket a molecule falls into. For finished runs exact counts
 * under High (SPEC.md §4); live runs bucket by per-molecule status.
 */
export function bucketOf(m: Molecule, runStatus: RunStatus): Bucket {
  if (runStatus === "finished") {
    const state = m.result?.state;
    if (state === "exact") return "high";
    if (state === "identified") {
      const conf = m.result?.confidence;
      if (conf == null) return "none";
      return confLabel(conf) === "high" ? "high" : confLabel(conf) === "medium" ? "medium" : "low";
    }
    if (state === "lead") return "low";
    return "none";
  }
  if (runStatus === "failed") return m.status === "searched" ? "searched" : "not_searched";
  if (m.status === "searched" || m.status === "done") return "searched";
  if (m.status === "searching") return "searching";
  return "waiting";
}

export function bucketsFor(runStatus: RunStatus): Bucket[] {
  return runStatus === "finished" ? DONE_BUCKETS : LIVE_BUCKETS;
}

export function counts(molecules: Molecule[], runStatus: RunStatus): Record<Bucket, number> {
  const out: Record<string, number> = {};
  for (const m of molecules) {
    const b = bucketOf(m, runStatus);
    out[b] = (out[b] ?? 0) + 1;
  }
  return out as Record<Bucket, number>;
}

/* ------------------------------------------------------------------ */
/* Row view                                                             */
/* ------------------------------------------------------------------ */

export interface RowView {
  molecule: Molecule;
  icon: IconKey;
  /** Second line: identified name (or status text while live). */
  line2: string;
  /** Score shown right-aligned, colour = label colour. null → nothing. */
  score: number | null;
  /** Tooltip wording for the score/icon ("Medium confidence"…). */
  hint: string;
}

const STATUS_LINE2: Record<string, string> = {
  waiting: "Waiting",
  searching: "Searching databases…",
  searched: "Searched, waiting for checks",
  not_searched: "Not searched",
};

const ICON_HINTS: Record<IconKey, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
  none: "Not identified",
  exact: "Exact match",
  waiting: "Waiting",
  searching: "Searching databases",
  searched: "Searched",
  not_searched: "Not searched",
  failed: "Failed",
};

/** Icon key for one row — confidence shapes for finished, status icons live. */
export function iconOf(m: Molecule, runStatus: RunStatus): IconKey {
  if (runStatus === "finished") {
    const state = m.result?.state;
    if (state === "exact") return "exact";
    if (state === "identified") {
      const conf = m.result?.confidence;
      if (conf == null) return "none";
      return confLabel(conf);
    }
    if (state === "lead") return "low";
    return "none";
  }
  if (runStatus === "failed") return m.status === "searched" ? "searched" : "not_searched";
  if (m.status === "done") return "searched";
  return m.status === "waiting" || m.status === "searching" || m.status === "searched"
    ? (m.status as IconKey)
    : "waiting";
}

export function rowOf(m: Molecule, runStatus: RunStatus): RowView {
  const icon = iconOf(m, runStatus);
  if (runStatus !== "finished") {
    return {
      molecule: m,
      icon,
      line2:
        runStatus === "failed" && m.status === "searched"
          ? "Searched, not checked"
          : (STATUS_LINE2[m.status] ?? STATUS_LINE2.waiting),
      score: null,
      hint: ICON_HINTS[icon],
    };
  }
  const r = m.result;
  const name = r?.name ?? (r?.best ? `${r.best.db} ${r.best.id}` : null);
  const line2 =
    r == null || r.state === "not_identified"
      ? "Not identified"
      : name && name !== m.display_name
        ? name
        : (r.description ?? name ?? "");
  const conf = r?.state === "exact" ? null : (r?.confidence ?? null);
  return {
    molecule: m,
    icon,
    line2,
    score: conf == null ? null : Math.round(conf),
    hint: ICON_HINTS[icon],
  };
}

/* ------------------------------------------------------------------ */
/* Search + filter                                                      */
/* ------------------------------------------------------------------ */

function haystack(m: Molecule): string {
  return [
    m.display_name,
    m.chain ? `chain ${m.chain}` : "",
    m.residue_names.join(" "),
    m.result?.name ?? "",
    m.result?.description ?? "",
    m.result?.best ? `${m.result.best.db} ${m.result.best.id}` : "",
    m.kind.replace(/_/g, " "),
    KIND_GROUP_LABELS[m.kind],
  ]
    .join(" ")
    .toLowerCase();
}

export function matches(m: Molecule, query: string): boolean {
  const q = query.trim().toLowerCase();
  return q === "" || haystack(m).includes(q);
}

/* ------------------------------------------------------------------ */
/* Kind grouping (default)                                              */
/* ------------------------------------------------------------------ */

export const KIND_ORDER: MoleculeKind[] = [
  "protein",
  "nucleic",
  "small_molecule",
  "lipid",
  "unknown",
  "ion",
  "water",
];

/** Ions and water start collapsed (SPEC.md §3.4). */
const START_COLLAPSED: ReadonlySet<MoleculeKind> = new Set(["ion", "water"]);

export interface KindGroup {
  key: MoleculeKind;
  title: string;
  rows: RowView[];
  /** Sum over member copies, for the collapsed-header "×N". */
  copies: number;
  defaultCollapsed: boolean;
}

export function kindGroups(molecules: Molecule[], runStatus: RunStatus): KindGroup[] {
  const byKind = new Map<MoleculeKind, Molecule[]>();
  for (const m of molecules) {
    const list = byKind.get(m.kind) ?? [];
    list.push(m); // keep file order
    byKind.set(m.kind, list);
  }
  return KIND_ORDER.filter((k) => byKind.has(k)).map((k) => {
    const members = byKind.get(k)!;
    return {
      key: k,
      title: KIND_GROUP_LABELS[k],
      rows: members.map((m) => rowOf(m, runStatus)),
      copies: members.reduce((n, m) => n + m.copies, 0),
      defaultCollapsed: START_COLLAPSED.has(k),
    };
  });
}

/* ------------------------------------------------------------------ */
/* Identification grouping (finished runs only, SPEC.md §3.4)           */
/* ------------------------------------------------------------------ */

export interface IdentRow {
  key: string;
  icon: IconKey;
  name: string;
  /** Number of member molecules ("NavMs ×4 chains"). */
  count: number;
  /** Sum over member copies (for copy-aware totals). */
  copies: number;
  memberLabels: string[];
  memberIds: string[];
  score: number | null;
  hint: string;
}

function identScore(m: Molecule): number {
  if (m.result?.state === "exact") return 100;
  if (m.result?.state === "identified") return m.result.confidence ?? 0;
  return -1; // lead → low number; not_identified → least certain
}

/** Merge rows sharing the same best database entry; least certain first. */
export function identGroups(molecules: Molecule[]): IdentRow[] {
  const groups = new Map<string, Molecule[]>();
  for (const m of molecules) {
    const best = m.result?.best;
    const key = m.result && best && m.result.state !== "not_identified"
      ? `${best.db}|${best.id}`
      : `none|${m.id}`;
    const list = groups.get(key) ?? [];
    list.push(m);
    groups.set(key, list);
  }
  const rows: IdentRow[] = [...groups.values()].map((members) => {
    const rep = [...members].sort((a, b) => identScore(b) - identScore(a))[0];
    const state = rep.result?.state ?? "not_identified";
    const name =
      state === "not_identified"
        ? rep.display_name
        : (rep.result?.name ??
          (rep.result?.best ? `${rep.result.best.db} ${rep.result.best.id}` : rep.display_name));
    const icon = iconOf(rep, "finished");
    return {
      key: members.map((x) => x.id).join("+"),
      icon,
      name,
      count: members.length,
      copies: members.reduce((n, x) => n + x.copies, 0),
      memberLabels: members.map((x) => x.display_name),
      memberIds: members.map((x) => x.id),
      score: state === "exact" || state === "not_identified" ? null : Math.round(rep.result?.confidence ?? 0),
      hint: ICON_HINTS[icon],
    };
  });
  rows.sort((a, b) => (a.score ?? -1) - (b.score ?? -1));
  return rows;
}

/* ------------------------------------------------------------------ */
/* Selection + persistence                                              */
/* ------------------------------------------------------------------ */

/** Default selection: first molecule that is not an ion or water (SPEC.md §3.4). */
export function defaultSelection(molecules: Molecule[]): string | null {
  const solute = molecules.filter((m) => m.kind !== "ion" && m.kind !== "water");
  // Open on an answer: the first identified molecule, not a fragment that
  // nothing matched (an 8-residue segment, a loader leftover).
  const identified = solute.find((m) => m.result?.state === "identified");
  return (identified ?? solute[0] ?? molecules[0])?.id ?? null;
}

export function applyQuery(molecules: Molecule[], bucket: Bucket | null, query: string, runStatus: RunStatus): Molecule[] {
  return molecules.filter((m) => (bucket == null || bucketOf(m, runStatus) === bucket) && matches(m, query));
}

export const COLLAPSED_STORAGE_PREFIX = "bioid:collapsed:";

export function loadCollapsed(storage: Storage | null, runId: string): Set<string> {
  if (!storage) return new Set();
  try {
    const raw = storage.getItem(COLLAPSED_STORAGE_PREFIX + runId);
    const arr = raw ? (JSON.parse(raw) as unknown) : [];
    return new Set(Array.isArray(arr) ? (arr as string[]) : []);
  } catch {
    return new Set();
  }
}

export function saveCollapsed(storage: Storage | null, runId: string, keys: Set<string>): void {
  if (!storage) return;
  try {
    storage.setItem(COLLAPSED_STORAGE_PREFIX + runId, JSON.stringify([...keys]));
  } catch {
    /* storage full / unavailable — collapsed state is best-effort */
  }
}
