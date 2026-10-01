/**
 * Frontpage run-config helpers.
 *
 * The pipeline's functional config is owned by the worker (config.ini). The UI
 * only edits the run-config JSON that is POSTed at submit time, so the keys
 * here must stay verbatim. `MINIMAL_DEFAULT_CONFIG` is the offline fallback,
 * extracted verbatim from the legacy frontpage (git tag ui-legacy-pre-rework,
 * ui/src/Pages/Frontpage.tsx) and used only when GET /runs/config/default
 * fails.
 */

export type ConfigValue = string | number | boolean | null;
export type ConfigSection = Record<string, unknown>;
export type RunConfig = Record<string, ConfigSection>;

/** The three executor flags that "Fast Mode" toggles (verbatim keys). */
export const FAST_MODE_FLAGS = [
  "signatures_parallel",
  "identifiers_parallel",
  "verification_parallel",
] as const;

/**
 * Fallback config used ONLY if the default-config endpoint is unavailable.
 * Must match the legacy MINIMAL_DEFAULT_CONFIG exactly (do not edit keys).
 */
export const MINIMAL_DEFAULT_CONFIG: RunConfig = {
  executor: {
    n_threads: 10,
    tps: 100,
    emit_queue_stats: true,
    signatures_parallel: false,
    identifiers_parallel: false,
    verification_parallel: false,
  },
  loader: {
    tpr_resid_from_one: true,
    guess_missing_elements: true,
    guess_missing_masses: true,
    guess_missing_names: true,
    guess_missing_bonds: false,
    quick_structure_search: true,
    element_mass_tolerance: 0.01,
    bond_guess_vdw_factor: 0.55,
    unwrap_periodic_boundaries: true,
    unwrap_compound: "fragments",
    unwrap_reference: "com",
    unwrap_selection: "all",
    unwrap_guess_bonds_if_missing: true,
    unwrap_warn_if_jumps_detected: true,
    unwrap_max_bond_length_factor: 0.5,
    unwrap_max_backbone_gap: 10.0,
  },
  signatures: {
    overwrite_existing: false,
    generation_attempts: 10,
    smiles_maximum_number_of_atoms: 250,
    fasta_map_determine_sequence_partial_mode: false,
    fasta_map_determine_sequence_strict_mode: false,
    name_minimum_length: 1,
    smiles: true,
    smiles_not_sanitized: true,
    atom: true,
    fasta_map_protein: true,
    fasta_map_nucleic: true,
    fasta_resname_protein: true,
    fasta_resname_nucleic: true,
    enhanced_nucleic_acid_recognition: true,
    pdb_protein: true,
    pdb_nucleic: true,
    pdb_not_sanitized_protein: true,
    pdb_not_sanitized_nucleic: true,
    pdb_backbone_protein: true,
    pdb_backbone_nucleic: true,
    pdb_backbone_not_sanitized_protein: true,
    pdb_backbone_not_sanitized_nucleic: true,
    name_chain: true,
    name_molecule: true,
    name_segment: true,
    fingerprint: true,
    inchi_key: true,
    morgan_fingerprint: true,
    selfies: true,
    molecular_formula: true,
    tdi: true,
    lipid_shorthand: true,
    glycan_composition: true,
    mmcif: true,
    topology_less_pdb: true,
    ca_only_pdb: true,
  },
  identifiers: {
    overwrite_existing: false,
    blast_pdb_protein: true,
    blast_pdb_protein_similarity: true,
    blast_uniprot: true,
    blast_uniprot_similarity: true,
    blast_pdb_nucleic: true,
    blast_pdb_nucleic_similarity: true,
    pdb_struct_protein: true,
    pdb_struct_protein_similarity: true,
    pdb_struct_nucleotide: true,
    pdb_struct_nucleotide_similarity: true,
    alphafind_struct: true,
    alphafind_struct_similarity: true,
    chembl_struct: true,
    chembl_struct_similarity: true,
    pubchem_struct: true,
    pubchem_struct_similarity: true,
    atom: true,
    atom_similarity: false,
    idsm_pubchem: true,
    idsm_pubchem_similarity: true,
    idsm_chembl: true,
    idsm_chembl_similarity: true,
    idsm_chebi: true,
    idsm_chebi_similarity: true,
    name_ccd: true,
    name_ccd_similarity: false,
    name_maps: true,
    name_maps_similarity: false,
    name_manual: true,
    name_manual_similarity: false,
  },
  verification: {
    verify_top_n: 100,
    similarity_top_n: 10,
    enable_annotation_quality: true,
    resolver_weight: 0.4,
    similarity_weight: 0.4,
    annotation_weight: 0.2,
    tm_score_threshold: 0.5,
    min_final_confidence: 0.0,
  },
  timeouts: {
    global_timeout_s: 600,
    input_timeout_s: 5,
    create_timeout_s: 5,
    load_timeout_s: 300,
    signatures_timeout_s: 2400,
    identifiers_timeout_s: 1200,
    summarize_timeout_s: 1200,
    metadata_timeout_s: 1200,
  },
};

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

/**
 * Return a copy of `config` with the Fast-Mode executor parallel flags set to
 * `enabled`. Does not mutate the input object.
 */
export function applyFastMode(config: RunConfig, enabled: boolean): RunConfig {
  const executor: ConfigSection = { ...(config.executor ?? {}) };
  for (const key of FAST_MODE_FLAGS) {
    executor[key] = enabled;
  }
  return { ...config, executor };
}

/** `some_field_name` -> "Some Field Name" (label rendering). */
export function humanLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Normalize the raw JSON body from GET /runs/config/default into a RunConfig.
 * The endpoint normally returns the section dict directly, but on error it
 * returns `{ error, config }`. Accepts both shapes; returns null when nothing
 * usable is present.
 */
export function parseConfigPayload(
  raw: unknown,
): RunConfig | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  const candidate = (typeof obj.config === "object" && obj.config)
    ? (obj.config as Record<string, unknown>)
    : obj;
  if (!candidate || typeof candidate !== "object") return null;
  const sections: Record<string, Record<string, unknown>> = {};
  let sawSection = false;
  for (const [key, value] of Object.entries(candidate)) {
    if (key.startsWith("_")) continue;
    if (value && typeof value === "object" && !Array.isArray(value)) {
      sections[key] = value as Record<string, unknown>;
      sawSection = true;
    }
  }
  return sawSection ? (sections as RunConfig) : null;
}

/**
 * Decide which config (if any) should be serialized into the POSTed
 * `config_json`. Per the contract, `config_json` is only sent when the config
 * was customized by the user or Fast Mode is on; otherwise the server applies
 * its own defaults.
 */
export function resolveConfigToPost(
  config: RunConfig | null,
  opts: { customized: boolean; fastMode: boolean },
): string | null {
  if (!config || Object.keys(config).length === 0) return null;
  if (!opts.customized && !opts.fastMode) return null;
  const final = opts.fastMode ? applyFastMode(config, true) : config;
  return JSON.stringify(final);
}

/**
 * Build the multipart FormData for POST /runs. Field names match the API:
 * `files` (repeatable), optional `run_name`, optional `config_json`.
 */
export function buildRunFormData(
  files: File[],
  runName: string | undefined | null,
  configJson: string | null,
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
  return form;
}
