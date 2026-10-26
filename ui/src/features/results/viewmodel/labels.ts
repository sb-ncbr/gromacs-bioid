/**
 * Display labels and static maps (bioid_ui_handoff/COPY.md §1, §2.6, §3.1;
 * DATA.md §2 database labels).
 */
import type { MoleculeKind } from "./types";

/** Database id → user-facing label (never show raw ids like PDB_ID). */
export const DB_LABELS: Record<string, string> = {
  pdb: "PDB",
  pdb_id: "PDB",
  uniprot: "UniProt",
  uniprot_id: "UniProt",
  pubchem_cid: "PubChem",
  pubchem: "PubChem",
  chembl: "ChEMBL",
  chebi: "ChEBI",
  alphafold: "AlphaFold DB",
  element: "Element",
};

/** Loader molecule type → view-model kind. */
export const KIND_MAP: Record<string, MoleculeKind> = {
  protein: "protein",
  nucleic: "nucleic",
  nucleic_acid: "nucleic",
  lipid: "lipid",
  ion: "ion",
  water: "water",
  solvent: "water",
  small_molecule: "small_molecule",
  ligand: "small_molecule",
  carbohydrate: "small_molecule",
  other: "unknown",
  unknown: "unknown",
};

/** Kind → group header wording (COPY.md §2.3). */
export const KIND_GROUP_LABELS: Record<MoleculeKind, string> = {
  protein: "Proteins",
  nucleic: "Nucleic acids",
  small_molecule: "Ligands and small molecules",
  lipid: "Lipids",
  unknown: "Other",
  ion: "Ions",
  water: "Water",
};

/** Singular kind wording for the answer-header eyebrow. */
export const KIND_LABELS: Record<MoleculeKind, string> = {
  protein: "protein",
  nucleic: "nucleic acid",
  small_molecule: "small molecule",
  lipid: "lipid",
  unknown: "molecule",
  ion: "ion",
  water: "water",
};

/** Input format display map (DATA.md §2). */
export const FORMAT_LABELS: Record<string, string> = {
  gromacs: "GROMACS",
  amber: "AMBER",
  pdb: "PDB",
  namd: "NAMD",
  charmm: "CHARMM",
  desmond: "Desmond",
  openmm: "OpenMM",
  tng: "TNG",
};

/** The six user-facing pipeline steps (COPY.md §2.1 step labels). */
export const STAGE_LABELS: Record<string, string> = {
  read: "Read files",
  find: "Find molecules",
  describe: "Describe molecules",
  search: "Search databases",
  check: "Check matches",
  save: "Prepare downloads",
};

/**
 * Resolver/service prefix → display name (COPY.md §3.1). Order matters:
 * first matching rule wins. Anything unmatched renders as "A database".
 */
export const SERVICE_LABELS: { pattern: RegExp; label: string }[] = [
  { pattern: /^blast_nr_protein/, label: "NCBI nr protein" },
  // swissprot IS UniProtKB; maps to the approved "UniProt" label (no new copy).
  { pattern: /uniprot|swissprot/i, label: "UniProt" },
  { pattern: /^(pdb_|rcsb_)/, label: "PDB" },
  { pattern: /^(alphafind|alphafold)/, label: "AlphaFold DB" },
  { pattern: /^pubchem/, label: "PubChem" },
  { pattern: /^chembl/, label: "ChEMBL" },
  { pattern: /^chebi/, label: "ChEBI" },
];
