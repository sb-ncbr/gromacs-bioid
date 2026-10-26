/**
 * Stage card model (SPEC.md §3.5, COPY.md §2.4–2.6) — pure derivations for
 * the answer header, the matches/sequence/chemistry/notes tabs, and the
 * "Same as" linkage. The components stay thin renderers.
 */
import type { Molecule, Note, ResultState } from "../viewmodel";
import { KIND_LABELS, confLabel } from "../viewmodel";
import { identGroups } from "../list/moleculeList";

/* ------------------------------------------------------------------ */
/* Answer header                                                        */
/* ------------------------------------------------------------------ */

/** Eyebrow: "Chain A · protein · 1 copy · 264 residues" (+ "· residue RN" for non-polymers). */
export function eyebrow(m: Molecule): string {
  const parts: string[] = [m.display_name, KIND_LABELS[m.kind]];
  parts.push(m.copies === 1 ? "1 copy" : `${m.copies.toLocaleString()} copies`);
  const isPolymer = m.kind === "protein" || m.kind === "nucleic";
  if (isPolymer && m.residues_per_copy != null) {
    parts.push(`${m.residues_per_copy.toLocaleString()} residues`);
  } else if (!isPolymer && m.atoms_per_copy > 0) {
    parts.push(`${m.atoms_per_copy.toLocaleString()} atoms per copy`);
  }
  if (!isPolymer && m.residue_names.length > 0) {
    parts.push(`residue ${m.residue_names[0]}`);
  }
  return parts.join(" · ");
}

export type BadgeKind = "high" | "medium" | "low" | "exact" | "none" | "status";

export interface Badge {
  kind: BadgeKind;
  /** Full wording for the right side of the answer header. */
  text: string;
  score: number | null;
}

/** The badge line (COPY.md §2.4). */
export function badgeOf(m: Molecule, runStatusResolved: boolean, statusText?: string): Badge {
  if (!runStatusResolved) {
    return { kind: "status", text: statusText ?? "Searching databases…", score: null };
  }
  const r = m.result;
  const state: ResultState = r?.state ?? "not_identified";
  if (state === "exact") return { kind: "exact", text: "Exact match", score: null };
  if (state === "not_identified") return { kind: "none", text: "No confident match", score: null };
  const conf = r?.confidence ?? 0;
  const label = state === "lead" ? "low" : confLabel(conf);
  const word = label === "high" ? "High" : label === "medium" ? "Medium" : "Low";
  return { kind: label, text: `${word} confidence ${Math.round(conf)} / 100`, score: Math.round(conf) };
}

/** Title + italic subtitle for the answer header. */
export function headline(m: Molecule, resolved: boolean): { title: string; sub: string | null } {
  if (!resolved) return { title: m.display_name, sub: null };
  const r = m.result;
  if (!r || r.state === "not_identified") {
    return { title: "Not identified", sub: "No database entry matched this molecule" };
  }
  const title = r.name ?? (r.best ? `${r.best.db} ${r.best.id}` : m.display_name);
  return { title, sub: r.description ?? null };
}

/** "Best match PDB 5HVX ↗" — null while running or when no match. */
export function bestLine(m: Molecule, resolved: boolean): { db: string; id: string; url: string } | null {
  if (!resolved || !m.result?.best) return null;
  return m.result.best;
}

/**
 * "Same as Chain B, Chain C and 1 more" — molecules sharing the same best
 * database entry (from the identification grouping, SPEC.md §3.5a).
 */
export function sameAs(molecules: Molecule[], selectedId: string): { id: string; label: string }[] {
  const groups = identGroups(molecules);
  const mine = groups.find((g) => g.memberIds.includes(selectedId));
  if (!mine || mine.memberIds.length < 2) return [];
  return mine.memberIds
    .filter((id) => id !== selectedId)
    .map((id) => ({ id, label: mine.memberLabels[mine.memberIds.indexOf(id)] }));
}

/* ------------------------------------------------------------------ */
/* Matches tab                                                          */
/* ------------------------------------------------------------------ */

/** Number of verified rows shown before "Show all N verified". */
export const MATCHES_VISIBLE = 5;

/* ------------------------------------------------------------------ */
/* Sequence / chemistry tab                                             */
/* ------------------------------------------------------------------ */

export function isPolymer(m: Molecule): boolean {
  return m.kind === "protein" || m.kind === "nucleic";
}

/** FASTA payload for copy/download: ">Chain A" + sequence wrapped at 80. */
export function fasta(m: Molecule): string | null {
  const seq = m.descriptor.sequence;
  if (!seq) return null;
  const lines = [`>${m.display_name}`];
  for (let i = 0; i < seq.length; i += 80) lines.push(seq.slice(i, i + 80));
  return lines.join("\n") + "\n";
}

export interface ChemRow {
  label: string;
  value: string;
  copiable: boolean;
}

/** Chemistry definition list (COPY.md §2.4 labels, fixed order). */
export function chemRows(m: Molecule): ChemRow[] {
  const d = m.descriptor;
  const rows: ChemRow[] = [];
  if (d.element) rows.push({ label: "Element", value: d.element, copiable: false });
  if (d.formula) rows.push({ label: "Formula", value: d.formula, copiable: true });
  if (d.smiles) rows.push({ label: "SMILES", value: d.smiles, copiable: true });
  if (d.inchikey) rows.push({ label: "InChIKey", value: d.inchikey, copiable: true });
  if (m.residue_names.length > 0) rows.push({ label: "Residue names", value: m.residue_names.join(", "), copiable: false });
  if (m.atoms_per_copy > 0) rows.push({ label: "Atoms per copy", value: String(m.atoms_per_copy), copiable: false });
  return rows;
}

/* ------------------------------------------------------------------ */
/* Notes tab (per molecule)                                             */
/* ------------------------------------------------------------------ */

/** Notes that affect this molecule, in display order. */
export function moleculeNotes(m: Molecule, all: Note[]): Note[] {
  const ids = new Set(m.note_ids);
  return all.filter((n) => ids.has(n.id) || n.affects.includes(m.id));
}

/* ------------------------------------------------------------------ */
/* Not-identified guidance (COPY.md §2.6, verbatim)                     */
/* ------------------------------------------------------------------ */

export const NOT_IDENTIFIED_POINTS: readonly string[] = [
  "Check that the residue name and topology describe the molecule you meant to simulate.",
  "Look at the candidates BioID rejected, with the reason for each.",
  "If you know what it is, describe it by hand when you deposit the simulation.",
];

export const CONFIDENCE_EXPLAINER = {
  summary: "What does confidence mean?",
  body: "How sure BioID is that the database entry is the molecule in your simulation, from 0 to 100. It combines how many independent searches proposed the entry, how closely the entry matches your molecule's sequence, structure or chemistry, and how well the entry is annotated.",
  legend: [
    { word: "High", range: "80–100", note: "reliable" },
    { word: "Medium", range: "50–79", note: "worth a quick check" },
    { word: "Low", range: "under 50", note: "a lead, not an answer" },
    { word: "Exact", range: null, note: "single-atom ions, identified by element" },
  ],
} as const;
