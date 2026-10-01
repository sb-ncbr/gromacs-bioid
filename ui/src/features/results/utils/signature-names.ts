/**
 * Human-readable names, groups, and file extensions for signature generators.
 *
 * Source of truth: .tmp/tasks/ui-rework/CONTEXT.md ("Display mappings" section).
 * Unknown generator keys fall back to a title-cased rendering of the raw key.
 */

/** Exact human names keyed by generator id (CONTEXT human-names table). */
const HUMAN_NAMES: Record<string, string> = {
  smiles: "SMILES",
  smiles_not_sanitized: "SMILES (raw)",
  fasta_map_protein: "Protein FASTA (sequence-mapped)",
  fasta_resname_protein: "Protein FASTA (residue names)",
  fasta_map_nucleic: "Nucleic FASTA (sequence-mapped)",
  fasta_resname_nucleic: "Nucleic FASTA (residue names)",
  pdb_protein: "PDB structure (protein)",
  pdb_nucleic: "PDB structure (nucleic)",
  pdb_backbone_protein: "PDB backbone trace (protein)",
  pdb_backbone_nucleic: "PDB backbone trace (nucleic)",
  topology_less_pdb: "Quick-search PDB (topology-less)",
  ca_only_pdb: "C\u03b1-only PDB",
  mmcif: "mmCIF structure",
  inchi_key: "InChIKey",
  molecular_formula: "Molecular formula",
  morgan_fingerprint: "Morgan fingerprint",
  selfies: "SELFIES",
  tdi: "Topological Descriptor Index",
  lipid_shorthand: "Lipid shorthand",
  glycan_composition: "Glycan composition",
  atom: "Atom counts",
  name_chain: "Name (chain)",
  name_molecule: "Name (molecule)",
  name_segment: "Name (segment)",
  fingerprint: "Fingerprint",
};

export type SignatureGroup =
  | "Sequence"
  | "Structure"
  | "Chemical"
  | "Fingerprint"
  | "Name"
  | "Domain"
  | "Basic"
  | "Other";

/** Title-case a snake_case key for unknown generators ("foo_bar" -> "Foo Bar"). */
function titleCase(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .split(" ")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** Human-readable display name for a signature generator. */
export function signatureName(key: string | null | undefined): string {
  if (!key) return "Signature";
  const known = HUMAN_NAMES[key];
  if (known) return known;
  const bb = key.match(/^pdb_backbone_(.+)$/);
  if (bb) return `PDB backbone trace (${bb[1]})`;
  return titleCase(key);
}

/** Group a signature generator belongs to (CONTEXT groups mapping). */
export function signatureGroup(key: string | null | undefined): SignatureGroup {
  if (!key) return "Other";
  if (key.startsWith("fasta")) return "Sequence";
  if (
    key.startsWith("pdb") ||
    key === "mmcif" ||
    key.startsWith("topology_less") ||
    key.startsWith("ca_only")
  ) {
    return "Structure";
  }
  if (
    key.startsWith("smiles") ||
    key.startsWith("inchi") ||
    key.startsWith("molecular_formula") ||
    key === "selfies" ||
    key.startsWith("formula")
  ) {
    return "Chemical";
  }
  if (key.startsWith("morgan") || key === "tdi" || key === "fingerprint") {
    return "Fingerprint";
  }
  if (key.startsWith("name_")) return "Name";
  if (key === "lipid_shorthand" || key === "glycan_composition") return "Domain";
  if (key === "atom") return "Basic";
  return "Other";
}

/** File extension for a signature (CONTEXT ext mapping). */
export function signatureExtension(key: string | null | undefined): string {
  if (!key) return ".txt";
  if (key.includes("fasta")) return ".fasta";
  if (key.startsWith("smiles")) return ".smi";
  if (key.includes("pdb")) return ".pdb";
  if (key === "mmcif") return ".cif";
  return ".txt";
}
