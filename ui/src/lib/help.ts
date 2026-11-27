/**
 * Info-button texts (2026-11-27 accessibility round). Each entry is a short
 * plain-language explanation plus the documentation section that says more.
 * `docs` is "<page>#<anchor>" in docs/site/docs; the anchors are explicit
 * `{#id}` or mkdocs heading slugs, checked by help.test.ts against the
 * Markdown so a renamed heading cannot leave a dead link.
 */

export interface HelpEntry {
  title: string;
  body: string;
  docs?: string;
}

/** Docs are served next to the app (components/shell/Header.tsx). */
export const DOCS_BASE = "/documentation/";

/** "index.md#confidence" -> "/documentation/#confidence" (mkdocs directory URLs). */
export function docsHref(docs: string): string {
  const [page, anchor] = docs.split("#");
  const path = page === "index.md" ? "" : `${page.replace(/\.md$/, "")}/`;
  return `${DOCS_BASE}${path}${anchor ? `#${anchor}` : ""}`;
}

export const HELP = {
  // -- results: the molecule list and the stage ---------------------------
  molecules: {
    title: "Molecules",
    body: "BioID splits the system into molecules from the bonds in your files. Identical copies are one row with a copy count; the kind (protein, lipid, ion, …) comes from residues and composition.",
    docs: "index.md#molecules",
  },
  wholeSystem: {
    title: "Whole system",
    body: "Every molecule of the simulation in one view, coloured by how confidently each was identified. Pick a molecule in the list or the viewer to see its matches.",
    docs: "index.md#molecules",
  },
  confidence: {
    title: "Confidence",
    body: "How sure BioID is that the entry is your molecule, 0–100. It combines how many independent searches proposed it, how closely it matches (sequence, structure or chemistry) and how complete the record is. High 80–100, Medium 50–79, Low under 50; Exact: ions matched by element.",
    docs: "index.md#confidence",
  },
  verified: {
    title: "Verified",
    body: "BioID fetched the entry's record again and compared it with your molecule. Only verified entries are shown as identifications; the others are rejected candidates.",
    docs: "index.md#verified",
  },
  entry: {
    title: "Entry",
    body: "The database and identifier of the match, linked to its record.",
    docs: "index.md#matches-table",
  },
  whatItIs: {
    title: "What it is",
    body: "The name of the database record, and its organism when known.",
    docs: "index.md#matches-table",
  },
  matchToMolecule: {
    title: "Match to your molecule",
    body: "What the comparison with your molecule found: sequence identity, same structure, a similar chemical skeleton (with its similarity), the same element, or the same fold (Foldseek, AlphaFind; stereochemistry not compared).",
    docs: "index.md#matches-table",
  },
  rejected: {
    title: "Rejected candidates",
    body: "Entries a search proposed that failed verification, with the reason. Leads for your own judgement, not identifications.",
    docs: "index.md#rejected",
  },
  notIdentified: {
    title: "Not identified",
    body: "No database entry passed verification: for example a designed or modified molecule no database holds, a misleading residue name, or a fragment too short to search.",
    docs: "index.md#not-identified",
  },
  coarseGrained: {
    title: "Coarse-grained model",
    body: "Beads stand for several atoms, so there is nothing atomistic to compare with a database structure. The name comes from the residue name and was not checked.",
    docs: "index.md#coarse-grained",
  },
  sequence: {
    title: "Sequence",
    body: "The sequence read from your files, per chain. This is what the sequence searches (BLAST, SIFTS) used.",
    docs: "index.md#descriptions",
  },
  chemistry: {
    title: "Chemistry",
    body: "Formula, SMILES and InChIKey worked out from the simulated structure: bond orders and charges perceived, united-atom hydrogens added back, stereochemistry from the 3D coordinates.",
    docs: "index.md#descriptions",
  },
  runProgress: {
    title: "Run progress",
    body: "Read files, find molecules, describe them, search the databases, check the matches, prepare downloads. Search steps have time limits; a run that reaches one still finishes, marked partial.",
    docs: "index.md#run-progress",
  },
  // -- technical details ----------------------------------------------------
  technical: {
    title: "Technical details",
    body: "Everything behind the results: how the files were read, every signature, every database search with its raw hits, and every candidate the verification checked.",
    docs: "index.md#technical-details",
  },
  signatures: {
    title: "Molecule descriptions",
    body: "Signatures: the sequences, structures, chemical identifiers and names generated for the molecule. Each database accepts some signature types.",
    docs: "identifiers.md#stage-1-signatures",
  },
  hitType: {
    title: "Hit type",
    body: "Identity: the search claims an exact match. Similarity: a ranked near neighbour (homologue, analogue, similar fold).",
    docs: "identifiers.md#hit-types",
  },
  resolver: {
    title: "Resolver",
    body: "The database search that returned the hit. The Databases page lists what each one searches.",
    docs: "databases.md#how-the-searches-are-ordered",
  },
  score: {
    title: "Score",
    body: "The search's own 0–100 score for the hit. It ranks hits within one search; the confidence is computed separately, at verification.",
    docs: "index.md#technical-details",
  },
  evalue: {
    title: "E-value",
    body: "BLAST: the number of hits this good expected by chance. Lower is better.",
    docs: "index.md#technical-details",
  },
  bitScore: {
    title: "Bit score",
    body: "BLAST: the alignment score normalised for the scoring system. Higher is better.",
    docs: "index.md#technical-details",
  },
  identityPct: {
    title: "Identity %",
    body: "BLAST: identical residues in the aligned region.",
    docs: "index.md#technical-details",
  },
  coveragePct: {
    title: "Coverage %",
    body: "BLAST: how much of your sequence the alignment covers.",
    docs: "index.md#technical-details",
  },
  similarity: {
    title: "Similarity",
    body: "How closely the fetched record matches your molecule, 0–100: sequence identity × coverage, structural TM-score, or chemical-skeleton fingerprint similarity.",
    docs: "identifiers.md#stage-3-verification",
  },
  identifierType: {
    title: "Type",
    body: "The kind of identifier: PDB entry, UniProt accession, PubChem compound, ChEMBL or ChEBI entry, AlphaFold model, element.",
    docs: "results-json.md#dataverification-the-identifications",
  },
  // -- front page -----------------------------------------------------------
  presets: {
    title: "Presets",
    body: "Ready-made settings: which databases are searched, and how many candidates are verified. Balanced suits most runs; Deep search is slower and finds rarer matches.",
    docs: "index.md#presets-and-advanced-configuration",
  },
  settings: {
    title: "Advanced configuration",
    body: "Per-run settings, starting from the preset: databases, verification, and how the files are read.",
    docs: "configuration.md#per-run-settings-and-presets",
  },
} as const satisfies Record<string, HelpEntry>;

export type HelpKey = keyof typeof HELP;

/** Documentation section of a configuration section (ConfigEditor). */
export const CONFIG_SECTION_DOCS: Record<string, string> = {
  identifiers: "databases.md#how-the-searches-are-ordered",
  verification: "configuration.md#verification",
  blast: "configuration.md#blast",
  pdb: "configuration.md#pdb-rcsb-structure-search",
};

/** Documentation section of a database group in the identifiers table. */
export const DATABASE_GROUP_DOCS: Record<string, string> = {
  Sequence: "databases.md#proteins-and-nucleic-acids",
  Structure: "databases.md#proteins-and-nucleic-acids",
  "Lipids and glycans": "databases.md#small-molecules-lipids-glycans-ions",
  Chemistry: "databases.md#small-molecules-lipids-glycans-ions",
  Names: "databases.md#small-molecules-lipids-glycans-ions",
};
