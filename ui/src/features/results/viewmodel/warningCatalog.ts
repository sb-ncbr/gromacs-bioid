/**
 * Warning/error catalogue (bioid_ui_handoff/COPY.md §3, verbatim wording).
 *
 * Placeholders filled by notes.ts / adapter.ts:
 *   {service}  display name from SERVICE_LABELS
 *   {n}        merged raw-message count
 *   {molecule} affected molecule display name (singular cases)
 *   {step}     one of the six step labels
 *   {short_id} run short id
 */

export interface CatalogEntry {
  severity: "error" | "attention" | "info" | "hidden";
  title: string;
  body: string;
  action: string | null;
}

const GENERIC_ERROR: CatalogEntry = {
  severity: "error",
  title: "Something went wrong on our side",
  body: "This was not caused by your files.",
  action: "Rerun. If it happens again, contact us and mention run {short_id}.",
};

const UNKNOWN_NOTE: CatalogEntry = {
  severity: "info",
  title: "Something unexpected happened during {step}",
  body: "Results may be incomplete.",
  action: "If results look wrong, contact us and mention run {short_id}.",
};

/** Exact-code entries. */
export const CATALOG: Record<string, CatalogEntry> = {
  identifier_resolver_failed: {
    severity: "attention",
    title: "{service} search did not finish",
    body: "The search was stopped or got no answer for {n} molecules. Matches from other databases are complete.",
    action: "Usually temporary. Rerun later if you need {service} matches.",
  },
  stage_time_budget: {
    severity: "attention",
    title: "Database search stopped early for {n} molecules",
    body: "The search hit its time limit before every service answered. Some matches for these molecules may be missing.",
    action: "Rerun later, or contact us if it happens again.",
  },
  verification_failed: {
    severity: "attention",
    title: "Matches for {molecule} could not be checked",
    body: "The candidate structures could not be compared with your molecule, so their confidence is lower than usual.",
    action: "Treat these matches with caution.",
  },
  signature_generator_failed: {
    severity: "info",
    title: "One chemical fingerprint could not be computed for {n} molecules",
    body: "Other descriptions of these molecules were used for searching. Exact-structure matches are unaffected.",
    action: null,
  },
  pbc_unwrap_applied: {
    severity: "info",
    title: "Molecules were made whole across the periodic box",
    body: "Some molecules crossed the box edge in your coordinates. BioID joined them before identification. Your files were not changed.",
    action: null,
  },
  pbc_jumps_detected: {
    severity: "attention",
    title: "Molecules are split across the periodic box",
    body: "Some molecules cross the box edge, which can split them into pieces.",
    action: "Fix before uploading: `gmx trjconv -pbc mol`, cpptraj `autoimage`, or VMD `pbc unwrap`.",
  },
  pbc_unwrap_failed: {
    severity: "attention",
    title: "Could not make molecules whole",
    body: "There is no box information, or molecules are too far apart. Split molecules may be identified wrongly.",
    action: "Fix periodic images before uploading (`gmx trjconv -pbc mol -ur compact`), then upload again.",
  },
  insufficient_bonds: {
    severity: "attention",
    title: "Few chemical bonds found in your file",
    body: "This usually means a PDB without CONECT records, so molecules may be split or merged.",
    action: "Upload a topology (.tpr, .prmtop, .psf) with the coordinates.",
  },
  geometry_scale_anomalous: {
    severity: "attention",
    title: "Coordinate units look wrong",
    body: "Atoms are closer together or further apart than expected.",
    action: "Check the units and upload again.",
  },
  system_export_failed: {
    severity: "info",
    title: "Some download files could not be created",
    body: "Identification results are unaffected.",
    action: null,
  },
  missing_input: {
    severity: "error",
    title: "No complete simulation found in your upload",
    body: "BioID needs a topology and coordinates, e.g. .tpr + .gro, .prmtop + .inpcrd, .psf + .pdb.",
    action: "Upload both files together.",
  },
  load_failed: {
    severity: "error",
    title: "Your files could not be read",
    body: "Files may be incomplete or mismatched, or in an unsupported variant.",
    action: "Check that the atom counts match and that all .itp files are included, or upload a .pdb of the first frame.",
  },
  worker_lost: {
    severity: "error",
    title: "The processing server stopped unexpectedly",
    body: "Your run stopped during {step}. This was a problem on our side, not with your files.",
    action: "Rerun to start again with the same files. If it happens twice, contact us and mention run {short_id}.",
  },
  missing_universe: GENERIC_ERROR,
  missing_facade: GENERIC_ERROR,
  unhandled_exception: GENERIC_ERROR,
  pipeline_execution_failed: GENERIC_ERROR,
};

/** Prefix-matched entries (e.g. every render_* failure). */
export const CATALOG_PREFIXES: { prefix: string; entry: CatalogEntry }[] = [
  {
    prefix: "render_",
    entry: {
      severity: "info",
      title: "Preview image could not be created",
      body: "Only the thumbnail in your run list is affected. Results and the 3D view are fine.",
      action: null,
    },
  },
];

/**
 * Codes never shown as notes: counted in hidden_note_count and visible only
 * under Technical details (COPY.md §3 "hidden" rows).
 */
export const HIDDEN_CODES: ReadonlySet<string> = new Set([
  "signature_generator_not_applicable",
  "coords_rescaled_nm_to_angstrom",
]);

/** Generic error-severity codes that collapse onto GENERIC_ERROR. */
export const GENERIC_ERROR_CODES: ReadonlySet<string> = new Set([
  "missing_universe",
  "missing_facade",
  "unhandled_exception",
  "pipeline_execution_failed",
]);

export function catalog(code: string): CatalogEntry {
  const exact = CATALOG[code];
  if (exact) return exact;
  const prefixed = CATALOG_PREFIXES.find((p) => code.startsWith(p.prefix));
  return prefixed ? prefixed.entry : UNKNOWN_NOTE;
}

/**
 * identifier_resolver_failed with `na_mode_unsupported` is a nucleotide
 * search on a protein, and with `no_polymer_payload` a structure search on
 * a small molecule: both are declared "not applicable" outcomes, not
 * failures, so they are hidden (COPY.md §3 / DATA.md §3.1). In g1 they were
 * the notes on 96% and 48% of runs.
 *
 * pbc_unwrap_failed with "No box information" means the input has no
 * periodic box, so nothing can be split across one; a real split is
 * reported separately as pbc_unwrap_incomplete.
 */
export function isHidden(code: string, message: string): boolean {
  if (HIDDEN_CODES.has(code)) return true;
  if (code === "identifier_resolver_failed"
      && (message.includes("na_mode_unsupported") || message.includes("no_polymer_payload"))) {
    return true;
  }
  if (code === "pbc_unwrap_failed" && message.includes("No box information")) {
    return true;
  }
  return false;
}
