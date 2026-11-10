/**
 * Frontpage run-config helpers.
 *
 * The pipeline's config is owned by the server (config.ini). GET
 * /runs/config/options returns the fields a run may change (with the server
 * defaults) and the presets; everything else (executables, database paths,
 * URLs, threads) is not offered and the API rejects changes to it. At submit
 * time only the fields that differ from the server defaults are POSTed.
 */

export type ConfigValue = string | number | boolean | null;
export type ConfigSection = Record<string, unknown>;
export type RunConfig = Record<string, ConfigSection>;

/** A run preset: overrides on top of the server defaults. */
export interface RunPreset {
  id: string;
  title: string;
  description: string;
  /** What the preset changes, in a sentence. */
  details?: string;
  /** lucide icon name (scale, zap, target, telescope). */
  icon: string;
  overrides: RunConfig;
}

export interface ConfigOptions {
  config: RunConfig;
  presets: RunPreset[];
}

/** Field-name hints that imply a non-negative numeric constraint. */
const NON_NEGATIVE_HINTS = [
  "timeout",
  "threshold",
  "max",
  "min",
  "weight",
  "limit",
  "count",
  "size",
  "factor",
  "tps",
  "n_threads",
  "top_n",
];

/** True when the given field name should be constrained to value >= 0. */
export function shouldRequireNonNegative(fieldName: string): boolean {
  const n = fieldName.toLowerCase();
  return NON_NEGATIVE_HINTS.some((h) => n.includes(h));
}

export interface NumberFieldResult {
  ok: boolean;
  /** Value to persist into the config (the previous value when invalid). */
  value: number;
  /** Raw text to display in the input. */
  display: string;
  error?: string;
}

/**
 * Validate a numeric config field. Mirrors the legacy rules: empty /
 * non-numeric input is rejected (previous value retained); fields whose name
 * implies a bound (timeouts, thresholds, min/max, weights, limits, counts,
 * sizes) may not be negative.
 */
export function validateNumberInput(
  raw: string,
  current: number,
  fieldName: string,
): NumberFieldResult {
  const trimmed = raw.trim();
  if (trimmed === "") {
    return { ok: false, value: current, display: raw, error: "Enter a number." };
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) {
    return { ok: false, value: current, display: raw, error: "Not a valid number." };
  }
  if (shouldRequireNonNegative(fieldName) && parsed < 0) {
    return {
      ok: false,
      value: current,
      display: raw,
      error: "Must be 0 or greater.",
    };
  }
  return { ok: true, value: parsed, display: String(parsed) };
}

/** Words shown in their usual spelling rather than title case. */
const WORDS: Record<string, string> = {
  tpr: "TPR", vdw: "vdW", smiles: "SMILES", pdb: "PDB", fasta: "FASTA", ca: "Cα", inchi: "InChI",
  mmcif: "mmCIF", blast: "BLAST", nr: "nr", nt: "nt", uniprot: "UniProt", swissprot: "Swiss-Prot",
  chembl: "ChEMBL", chebi: "ChEBI", pubchem: "PubChem", idsm: "IDSM", ccd: "CCD", alphafind: "AlphaFind",
  rcsb: "RCSB", tm: "TM", tdi: "TDI", selfies: "SELFIES", aa: "aa", fp: "fingerprint", n: "number of",
  tps: "TPS", api: "API", struct: "structure", hfamily: "H-family", inchikey: "InChIKey",
  sifts: "SIFTS", uniref50: "UniRef50", swisslipids: "SwissLipids", "3di": "3Di",
  evalue: "E-value", cov: "coverage",
};

/** Labels for fields whose key reads badly through humanLabel. */
const FIELD_LABEL: Record<string, string> = {
  "verification.verify_top_n": "Candidates verified per molecule",
  "verification.verify_top_n_supplementary": "Extra candidates from supplementary databases",
  "verification.similarity_top_n": "Similar matches kept per molecule",
  "verification.min_final_confidence": "Minimum confidence",
  "verification.tm_score_threshold": "Minimum TM-score",
  "verification.enable_annotation_quality": "Score annotation quality",
  "verification.annotation_live_fetch": "Fetch missing annotations live",
  "pdb.rcsb_include_mixed_complexes": "Include protein–nucleic acid complexes",
  "signatures.fasta_map_determine_sequence_partial_mode": "Partial protein sequences",
  "signatures.fasta_map_determine_sequence_strict_mode": "Strict protein sequences",
};

/** Label of `section.field` in the editor. */
export function fieldLabel(section: string, field: string): string {
  return FIELD_LABEL[`${section}.${field}`] ?? humanLabel(field);
}

/**
 * Config key → label: "global_timeout_s" → "Global timeout (s)",
 * "tpr_resid_from_one" → "TPR resid from one". Sentence case, known
 * acronyms kept, the unit suffix shown as a unit.
 */
export function humanLabel(key: string): string {
  const unit = /_s$/.test(key) ? " (s)" : /_p$/.test(key) ? " (0–1)" : "";
  const words = key.replace(/_(s|p)$/, "").split("_").filter(Boolean);
  const text = words
    .map((w, i) => {
      const known = WORDS[w.toLowerCase()];
      if (known) return known;
      return i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w;
    })
    .join(" ");
  return text + unit;
}

/** What each config section controls (one line under its heading). */
export const SECTION_HELP: Record<string, string> = {
  identifiers: "Which databases are searched: for identical entries (exact) and for similar ones.",
  verification: "How many candidates are checked against the database records, and how they are scored.",
  blast: "When a sequence match counts as exact or as similar.",
  chembl: "ChEMBL similarity search.",
  idsm: "IDSM chemical similarity search.",
  pubchem: "PubChem similarity search.",
  pdb: "RCSB PDB structure search.",
  signatures: "How protein and nucleic-acid sequences are read from the structure.",
  loader: "How the simulation files are read: missing elements, bonds and periodic unwrapping.",
};

/** Identifier toggles grouped by kind of search (unlisted ones: "Other"). */
const IDENTIFIER_GROUPS: [string, RegExp][] = [
  ["Sequence", /^(blast_|sifts_)/],
  ["Structure", /^(pdb_struct_|alphafind_|foldseek_|mmcif_)/],
  ["Lipids and glycans", /^(lipid_|swisslipids|glycan_)/],
  ["Chemistry", /^(pubchem_|chembl_|idsm_|inchikey_|formula_|chebi_|atom$)/],
  ["Names", /^name_/],
];

export interface IdentifierRow {
  /** Resolver name; the similarity toggle is `${name}_similarity`. */
  name: string;
  exact?: boolean;
  similar?: boolean;
}

/**
 * The identifiers section as rows of (exact, similar) toggles, grouped by
 * kind of search, in the server's order within each group.
 */
export function identifierGroups(section: ConfigSection): [string, IdentifierRow[]][] {
  const rows = new Map<string, IdentifierRow>();
  for (const [key, value] of Object.entries(section)) {
    if (typeof value !== "boolean") continue;
    const similar = key.endsWith("_similarity");
    const name = similar ? key.slice(0, -"_similarity".length) : key;
    const row = rows.get(name) ?? { name };
    if (similar) row.similar = value;
    else row.exact = value;
    rows.set(name, row);
  }
  const groups = new Map<string, IdentifierRow[]>();
  for (const [title] of IDENTIFIER_GROUPS) groups.set(title, []);
  groups.set("Other", []);
  for (const row of rows.values()) {
    const title = IDENTIFIER_GROUPS.find(([, re]) => re.test(row.name))?.[0] ?? "Other";
    groups.get(title)!.push(row);
  }
  return [...groups.entries()].filter(([, r]) => r.length > 0);
}

/**
 * Per-field help text for ConfigEditor, keyed "section.field"
 * (v3.142 Phase 3). Backend doctrine: the three confidence weights are
 * normalized by their sum at use-time (raw values are recorded in the
 * run's verification/_meta for provenance); all-zero falls back to equal
 * thirds — so only the ratio matters here.
 */
export const FIELD_HELP: Record<string, string> = {
  "verification.verify_top_n":
    "Candidate groups per molecule checked against their database records. More finds rarer matches but is slower.",
  "verification.verify_top_n_supplementary":
    "Extra groups found only by the supplementary and slow databases, checked after the main window.",
  "verification.similarity_top_n": "Similar (non-identical) matches kept per molecule.",
  "verification.min_final_confidence": "Matches below this confidence (0–100) are not marked verified.",
  "verification.tm_score_threshold": "Minimum TM-score (0–1) for a structure match to count.",
  "verification.resolver_weight":
    "Weight of the database-belief term (resolver agreement structure). Weights are normalized by their sum at runtime — only the ratio matters; all-zero falls back to equal thirds.",
  "verification.similarity_weight":
    "Weight of the match term (worker measurement: fingerprint Tanimoto / alignment identity-coverage / TM-score). Normalized by the sum with the other weights.",
  "verification.annotation_weight":
    "Weight of the annotation term (completeness of the database record). Normalized by the sum with the other weights.",
  "verification.annotation_live_fetch":
    "Fetch annotation details missing from the local database copies from the live services (bounded; falls back silently).",
  "loader.quick_structure_search":
    "Skip bond guessing and search with simplified structures (topology-less and Cα-only PDB). Faster on large systems.",
  "pdb.rcsb_include_mixed_complexes": "Also search PDB entries that mix protein and nucleic acid.",
  "signatures.fasta_map_determine_sequence_strict_mode": "Protein sequences must start with methionine.",
  "signatures.fasta_map_determine_sequence_partial_mode":
    "Allow a protein sequence shorter than the number of residues in the molecule.",
  "chembl.similarity_threshold": "Minimum similarity (%) for a similar compound.",
  "idsm.similarity_threshold": "Minimum similarity (%) for a similar compound.",
  "pubchem.similarity_threshold": "Minimum similarity (%) for a similar compound.",
};

export interface WeightTriple {
  resolver_weight?: number;
  similarity_weight?: number;
  annotation_weight?: number;
}

/**
 * Effective (sum-normalized) confidence weights — mirrors
 * verification.manager.normalize_weights so the UI can preview exactly
 * what the run will use. Returns null when any field is not a finite
 * number; all-zero/negative falls back to equal thirds.
 */
export function normalizedWeights(v: WeightTriple): [number, number, number] | null {
  const raw = [v.resolver_weight, v.similarity_weight, v.annotation_weight];
  if (raw.some((w) => typeof w !== "number" || !isFinite(w as number))) return null;
  const cleaned = raw.map((w) => ((w as number) > 0 ? (w as number) : 0));
  const total = cleaned.reduce((a, b) => a + b, 0);
  if (total <= 0) return [1 / 3, 1 / 3, 1 / 3];
  return [cleaned[0] / total, cleaned[1] / total, cleaned[2] / total];
}

function sectionsOf(raw: unknown): RunConfig | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const sections: RunConfig = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    if (key.startsWith("_")) continue;
    if (value && typeof value === "object" && !Array.isArray(value)) {
      sections[key] = value as ConfigSection;
    }
  }
  return Object.keys(sections).length > 0 ? sections : null;
}

/** Normalize the JSON body of GET /runs/config/options; null if unusable. */
export function parseConfigOptions(raw: unknown): ConfigOptions | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  const config = sectionsOf(obj.config);
  if (!config) return null;
  const presets = Array.isArray(obj.presets)
    ? (obj.presets as RunPreset[]).filter(
        (p) => p && typeof p.id === "string" && typeof p.title === "string",
      ).map((p) => ({ ...p, overrides: sectionsOf(p.overrides) ?? {} }))
    : [];
  return { config, presets };
}

export function cloneConfig(cfg: RunConfig): RunConfig {
  return JSON.parse(JSON.stringify(cfg)) as RunConfig;
}

/** `base` with the preset's overrides applied (new object). */
export function applyPreset(base: RunConfig, preset: RunPreset): RunConfig {
  const out = cloneConfig(base);
  for (const [section, fields] of Object.entries(preset.overrides)) {
    out[section] = { ...(out[section] ?? {}), ...fields };
  }
  return out;
}

/** The fields of `config` that differ from `base`, as {section: {field: value}}. */
export function configDiff(config: RunConfig, base: RunConfig): RunConfig {
  const diff: RunConfig = {};
  for (const [section, fields] of Object.entries(config)) {
    for (const [field, value] of Object.entries(fields)) {
      if (base[section]?.[field] !== value) {
        (diff[section] ??= {})[field] = value;
      }
    }
  }
  return diff;
}

function sameDiff(a: RunConfig, b: RunConfig): boolean {
  const flat = (d: RunConfig) =>
    Object.entries(d)
      .flatMap(([s, f]) => Object.entries(f).map(([k, v]) => `${s}.${k}=${JSON.stringify(v)}`))
      .sort()
      .join("\n");
  return flat(a) === flat(b);
}

/** The preset `config` is exactly equal to, or null for a custom config. */
export function activePresetId(
  config: RunConfig,
  base: RunConfig,
  presets: RunPreset[],
): string | null {
  const diff = configDiff(config, base);
  const hit = presets.find((p) => sameDiff(diff, configDiff(applyPreset(base, p), base)));
  return hit ? hit.id : null;
}

/**
 * The `config_json` to POST: only the fields that differ from the server
 * defaults, or null when nothing changed (the server then uses its own).
 */
export function resolveConfigToPost(config: RunConfig | null, base: RunConfig | null): string | null {
  if (!config || !base) return null;
  const diff = configDiff(config, base);
  return Object.keys(diff).length > 0 ? JSON.stringify(diff) : null;
}

/**
 * Build the multipart FormData for POST /runs. Field names match the API:
 * `files` (repeatable), optional `run_name`, `config_json`, `preset`
 * (recorded with the run; the overrides it implies are in config_json too)
 * and `retention` ("" = the 30-day default, "preserve", or days).
 */
export function buildRunFormData(
  files: File[],
  runName: string | undefined | null,
  configJson: string | null,
  preset?: string | null,
  retention?: string | null,
): FormData {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  if (runName && runName.trim()) {
    form.append("run_name", runName.trim());
  }
  if (configJson) {
    form.append("config_json", configJson);
  }
  if (preset) {
    form.append("preset", preset);
  }
  if (retention) {
    form.append("retention", retention);
  }
  return form;
}
