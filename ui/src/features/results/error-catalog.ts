/**
 * Error catalog → plain-language copy binding.
 *
 * Source of truth: .tmp/tasks/ui-rework/errors/error-catalog.json v2 (planner-owned).
 * The worker emits `code` + `details` (and `step_id`) on warnings and
 * critical errors; this module maps each code to audience-safe copy and knows
 * which detail keys are worth surfacing. Unknown codes fall back to a friendly
 * title-cased rendering of the raw code.
 */

export interface CatalogStage {
  group: string;
  display: string;
  tasks: string[];
}

export interface CatalogCode {
  code: string;
  kind: "warning" | "info" | "critical";
  /** Stage group id this code belongs to, or "*" for any stage. */
  stage: string;
  user_title: string;
  user_what: string;
  user_action: string | null;
  details_show: string[];
  raw_error_map?: Record<string, string>;
}

/**
 * Human-readable names for resolver identifiers (v2 catalog, 21 entries).
 * Used to translate internal resolver keys into plain-language descriptions.
 */
export const RESOLVER_HUMAN_NAMES: Record<string, string> = {
  blast_nr_protein: "BLAST search of the NR protein database",
  blast_pdb_protein: "protein structure search in PDB",
  blast_pdb_nucleic: "nucleic structure search in PDB",
  blast_uniprot: "BLAST search of UniProt",
  blast_swissprot_protein: "BLAST search of Swiss-Prot",
  pdb_struct_protein: "protein structure similarity search in PDB",
  pdb_struct_nucleotide: "nucleotide structure similarity search in PDB",
  alphafind_struct: "AlphaFind structure similarity search",
  chembl_struct: "ChEMBL chemical database search",
  pubchem_struct: "PubChem chemical database search",
  idsm_pubchem: "PubChem similarity search",
  idsm_chembl: "ChEMBL similarity search",
  idsm_chebi: "ChEBI similarity search",
  formula_pubchem: "PubChem formula search",
  formula_pubchem_local: "PubChem formula search (local mirror)",
  formula_chembl: "ChEMBL formula search",
  formula_hfamily: "formula search (host-guest family)",
  mmcif_struct: "mmCIF structure search",
  name_ccd: "ligand name lookup (CCD)",
  name_maps: "name lookup",
  name_manual: "manual name lookup",
};

/**
 * Translate a resolver key to its human-readable name.
 * Falls back to the raw resolver name if not in the map.
 */
export function resolverHumanName(resolver?: string | null): string {
  if (!resolver) return "a search";
  return RESOLVER_HUMAN_NAMES[resolver] ?? resolver;
}

/**
 * Parse a resolver failure message of the form:
 *   "{resolver} ({generator}): {error}"
 * Returns extracted parts; empty strings if the format doesn't match.
 */
export function parseResolverMessage(message: string): {
  resolver: string;
  generator: string;
  error: string;
} {
  const m = message.match(/^\s*([\w-]+)\s*\(([^)]*)\)\s*:\s*(.*)$/s);
  if (!m) return { resolver: "", generator: "", error: message };
  return { resolver: m[1], generator: m[2], error: m[3].trim() };
}

/**
 * Parse a signature generator failure message of the form:
 *   "{generator}: {error}"
 */
export function parseGeneratorMessage(message: string): {
  generator: string;
  error: string;
} {
  const m = message.match(/^\s*([\w-]+)\s*:\s*(.*)$/s);
  if (!m) return { generator: "", error: message };
  return { generator: m[1], error: m[2].trim() };
}

/**
 * Determine a human-readable reason from the raw error message by
 * substring-matching against the raw_error_map (case-insensitive).
 * Falls back to "did not finish".
 */
export function reasonHumanName(
  error: string | null | undefined,
  rawErrorMap?: Record<string, string>,
): string {
  if (!error || !rawErrorMap) return "did not finish";
  const lowerError = error.toLowerCase();
  for (const [pattern, label] of Object.entries(rawErrorMap)) {
    if (lowerError.includes(pattern.toLowerCase())) return label;
  }
  return "did not finish";
}

/**
 * Sanitize a technical detail string by stripping /app/... filesystem paths
 * so internal paths are never rendered in the UI.
 */
export function sanitizeTechnicalDetail(message: string | null | undefined): string {
  if (!message) return "";
  return message
    .replace(/\/app\/[^\s"'`)\]<>]+/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** The 5 canonical pipeline stage groups (order = display order). */
export const CATALOG_STAGES: CatalogStage[] = [
  {
    group: "prepare",
    display: "Prepare structure",
    tasks: ["discover_input", "load_simulation", "repair_topology", "unwrap_periodic_boundaries", "analyze_universe"],
  },
  { group: "signatures", display: "Generate signatures", tasks: ["generate_signatures"] },
  { group: "identify", display: "Identify molecules", tasks: ["identify_molecules"] },
  { group: "verify", display: "Verify results", tasks: ["verify_results"] },
  { group: "export", display: "Export results", tasks: ["export_results", "render_png"] },
];

export const CATALOG_CODES: CatalogCode[] = [
  {
    code: "insufficient_bonds",
    kind: "warning",
    stage: "prepare",
    user_title: "Bond information looks incomplete",
    user_what:
      "The structure has very few chemical bonds, which usually happens with PDB files that lack CONECT records. Molecule detection may be unreliable.",
    user_action: "Re-run with 'Guess missing bonds' enabled (Advanced configuration → Loader).",
    details_show: ["bond_count", "atom_count"],
  },
  {
    code: "pbc_jumps_detected",
    kind: "warning",
    stage: "prepare",
    user_title: "Structure appears split across periodic boundaries",
    user_what: "Molecules look broken across the edges of the simulation box.",
    user_action: "Re-run with 'Unwrap periodic boundaries' enabled (Advanced configuration → Loader).",
    details_show: ["bond_jumps", "backbone_jumps"],
  },
  {
    code: "pbc_unwrap_applied",
    kind: "info",
    stage: "prepare",
    user_title: "Structure was made whole",
    user_what: "Periodic boundary unwrapping was applied to make molecules whole.",
    user_action: null,
    details_show: [],
  },
  {
    code: "pbc_unwrap_failed",
    kind: "warning",
    stage: "prepare",
    user_title: "Could not repair periodic boundaries",
    user_what: "Unwrapping was enabled but did not succeed; some molecules may still appear split.",
    user_action: "Re-run; contact us if it repeats.",
    details_show: [],
  },
  {
    code: "signature_generator_failed",
    kind: "info",
    stage: "signatures",
    user_title: "A signature was skipped",
    user_what: "The {generator_human} signature does not apply to this molecule, so it was skipped. This is expected by design - other signatures were still generated and used.",
    user_action: null,
    details_show: ["generator_human"],
  },
  {
    code: "identifier_resolver_failed",
    kind: "warning",
    stage: "identify",
    user_title: "A search did not finish",
    user_what: "The {resolver_human} did not complete ({reason_human}), so some matches may be missing.",
    user_action: "Usually nothing is wrong with your data. You can re-run the annotation for a complete search.",
    details_show: ["resolver_human", "reason_human"],
    raw_error_map: {
      "file is not a database": "temporarily unavailable",
      "timed out": "took too long and was stopped",
      "BLAST timed out": "took too long and was stopped",
    },
  },
  {
    code: "verification_failed",
    kind: "warning",
    stage: "verify",
    user_title: "Verification failed for one molecule",
    user_what: "Segment {segment} could not be verified; its matches may be less reliable.",
    user_action: null,
    details_show: ["segment"],
  },
  {
    code: "stage_time_budget",
    kind: "warning",
    stage: "*",
    user_title: "A step ran over its time budget",
    user_what: "The step continued with partial results; some searches may be incomplete.",
    user_action: "Re-running may produce more complete results.",
    details_show: ["stage"],
  },
  {
    code: "system_export_failed",
    kind: "warning",
    stage: "export",
    user_title: "Export problem",
    user_what: "Some downloadable output files may be missing.",
    user_action: "Re-run if you need the exports.",
    details_show: [],
  },
  {
    code: "segment_export_failed",
    kind: "warning",
    stage: "export",
    user_title: "Export problem for one segment",
    user_what: "Some downloadable files for segment {segment} may be missing.",
    user_action: null,
    details_show: ["segment"],
  },
  {
    code: "missing_input",
    kind: "critical",
    stage: "prepare",
    user_title: "Input files could not be understood",
    user_what: "The uploaded files did not form a loadable simulation input.",
    user_action: "Include a topology (.tpr or .top with all .itp includes) and ideally a .gro file — or upload everything as a .zip.",
    details_show: [],
  },
  {
    code: "load_failed",
    kind: "critical",
    stage: "prepare",
    user_title: "Simulation files could not be loaded",
    user_what: "Several loading strategies were tried and none succeeded.",
    user_action: "Check the Input & Files tab for what was uploaded and try a different/complete file set.",
    details_show: ["attempts"],
  },
  {
    code: "missing_universe",
    kind: "critical",
    stage: "prepare",
    user_title: "Internal processing error",
    user_what: "The loaded structure was not available to a later step.",
    user_action: "Please re-run; contact us if it repeats.",
    details_show: [],
  },
  {
    code: "missing_facade",
    kind: "critical",
    stage: "*",
    user_title: "Internal processing error",
    user_what: "A processing component was unavailable mid-run.",
    user_action: "Please re-run; contact us if it repeats.",
    details_show: [],
  },
  {
    code: "unhandled_exception",
    kind: "critical",
    stage: "*",
    user_title: "Unexpected error",
    user_what: "Something went wrong that we did not anticipate.",
    user_action: "Please re-run; contact us with the run ID if it repeats.",
    details_show: [],
  },
  {
    code: "pipeline_execution_failed",
    kind: "critical",
    stage: "*",
    user_title: "Unexpected error",
    user_what: "The processing job failed before completion.",
    user_action: "Please re-run; contact us with the run ID if it repeats.",
    details_show: [],
  },
];

/** Title-case a snake_case code for unknown codes ("foo_bar" → "Foo Bar"). */
export function titleCase(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .split(" ")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** Look up a catalog entry by code (undefined when unknown). */
export function getCatalogEntry(code: string | null | undefined): CatalogCode | undefined {
  if (!code) return undefined;
  return CATALOG_CODES.find((c) => c.code === code);
}

/**
 * Per-token fallback so that a missing detail still reads naturally.
 * Applied only when `details` does not carry a value for the token.
 */
const TOKEN_FALLBACK: Record<string, string> = {
  generator_human: "requested",
  resolver: "a",
  segment: "the affected",
  stage: "a",
};

/**
 * Replace `{token}` placeholders in a template with values from `details`.
 * Missing tokens fall back to a friendly word (or are dropped), so the copy
 * never shows a raw `{token}`.
 */
export function interpolate(
  template: string,
  details: Record<string, unknown> | null | undefined,
): string {
  if (!template) return "";
  const d = details ?? {};
  return template.replace(/\{([a-zA-Z0-9_]+)\}/g, (_m, token: string) => {
    const v = d[token];
    if (v != null && v !== "") {
      const s = String(v).trim();
      if (s) return s;
    }
    return TOKEN_FALLBACK[token] ?? "";
  });
}

/**
 * Format the subset of `details` worth surfacing for a code, e.g.
 * "bond_count = 0 · atom_count = 2760". Returns "" when nothing to show.
 */
export function formatDetails(
  entry: CatalogCode,
  details: Record<string, unknown> | null | undefined,
): string {
  const d = details ?? {};
  const parts: string[] = [];
  for (const key of entry.details_show) {
    const v = d[key];
    if (v != null && v !== "") {
      parts.push(`${key} = ${String(v)}`);
    }
  }
  return parts.join(" · ");
}

/** Map a stage group id to its human display name (fallback: the id). */
export function stageDisplay(group: string): string {
  const s = CATALOG_STAGES.find((x) => x.group === group);
  return s ? s.display : titleCase(group);
}

/**
 * Determine which stage group a warning/critical error belongs to.
 * Prefers the catalog's stage when it names a real group; otherwise derives
 * the group from the emitting task (`step_id`); otherwise "pipeline".
 */
export function stageForCode(
  code: string | null | undefined,
  stepId: string | null | undefined,
): string {
  const entry = getCatalogEntry(code);
  if (entry && entry.stage !== "*") return entry.stage;
  if (stepId) {
    const s = CATALOG_STAGES.find((g) => g.tasks.includes(stepId));
    if (s) return s.group;
  }
  return "pipeline";
}
