import { describe, expect, it } from "vitest";
import { signatureExtension, signatureGroup, signatureName } from "./signature-names";

describe("signatureName", () => {
  it("returns exact names from the map", () => {
    expect(signatureName("smiles")).toBe("SMILES");
    expect(signatureName("smiles_not_sanitized")).toBe("SMILES (raw)");
    expect(signatureName("fasta_map_protein")).toBe("Protein FASTA (sequence-mapped)");
    expect(signatureName("pdb_protein")).toBe("PDB structure (protein)");
    expect(signatureName("pdb_nucleic")).toBe("PDB structure (nucleic)");
    expect(signatureName("mmcif")).toBe("mmCIF structure");
    expect(signatureName("inchi_key")).toBe("InChIKey");
    expect(signatureName("molecular_formula")).toBe("Molecular formula");
    expect(signatureName("morgan_fingerprint")).toBe("Morgan fingerprint");
    expect(signatureName("selfies")).toBe("SELFIES");
    expect(signatureName("tdi")).toBe("Topological Descriptor Index");
    expect(signatureName("lipid_shorthand")).toBe("Lipid shorthand");
    expect(signatureName("glycan_composition")).toBe("Glycan composition");
    expect(signatureName("atom")).toBe("Atom counts");
    expect(signatureName("name_chain")).toBe("Name (chain)");
    expect(signatureName("name_molecule")).toBe("Name (molecule)");
    expect(signatureName("name_segment")).toBe("Name (segment)");
    expect(signatureName("fingerprint")).toBe("Fingerprint");
    expect(signatureName("topology_less_pdb")).toBe("Quick-search PDB (topology-less)");
    expect(signatureName("ca_only_pdb")).toBe("C\u03b1-only PDB");
  });

  it("returns Title Case for unknown keys", () => {
    expect(signatureName("some_new_sig")).toBe("Some New Sig");
    expect(signatureName("foo")).toBe("Foo");
  });

  it("handles pdb_backbone_* pattern", () => {
    expect(signatureName("pdb_backbone_protein")).toBe("PDB backbone trace (protein)");
    expect(signatureName("pdb_backbone_nucleic")).toBe("PDB backbone trace (nucleic)");
    expect(signatureName("pdb_backbone_other")).toBe("PDB backbone trace (other)");
  });

  it("handles null/undefined gracefully", () => {
    expect(signatureName(null)).toBe("Signature");
    expect(signatureName(undefined)).toBe("Signature");
    expect(signatureName("")).toBe("Signature");
  });
});

describe("signatureGroup", () => {
  it("maps fasta generators to Sequence", () => {
    expect(signatureGroup("fasta_map_protein")).toBe("Sequence");
    expect(signatureGroup("fasta_resname_nucleic")).toBe("Sequence");
  });

  it("maps structure generators to Structure", () => {
    expect(signatureGroup("pdb_protein")).toBe("Structure");
    expect(signatureGroup("pdb_nucleic")).toBe("Structure");
    expect(signatureGroup("mmcif")).toBe("Structure");
    expect(signatureGroup("topology_less_pdb")).toBe("Structure");
    expect(signatureGroup("ca_only_pdb")).toBe("Structure");
  });

  it("maps chemical generators to Chemical", () => {
    expect(signatureGroup("smiles")).toBe("Chemical");
    expect(signatureGroup("smiles_not_sanitized")).toBe("Chemical");
    expect(signatureGroup("inchi_key")).toBe("Chemical");
    expect(signatureGroup("molecular_formula")).toBe("Chemical");
    expect(signatureGroup("selfies")).toBe("Chemical");
  });

  it("maps fingerprint generators to Fingerprint", () => {
    expect(signatureGroup("morgan_fingerprint")).toBe("Fingerprint");
    expect(signatureGroup("tdi")).toBe("Fingerprint");
    expect(signatureGroup("fingerprint")).toBe("Fingerprint");
  });

  it("maps name generators to Name", () => {
    expect(signatureGroup("name_chain")).toBe("Name");
    expect(signatureGroup("name_molecule")).toBe("Name");
    expect(signatureGroup("name_segment")).toBe("Name");
  });

  it("maps domain generators to Domain", () => {
    expect(signatureGroup("lipid_shorthand")).toBe("Domain");
    expect(signatureGroup("glycan_composition")).toBe("Domain");
  });

  it("maps atom to Basic", () => {
    expect(signatureGroup("atom")).toBe("Basic");
  });

  it("returns Other for unknown keys", () => {
    expect(signatureGroup("unknown_sig")).toBe("Other");
    expect(signatureGroup(null)).toBe("Other");
    expect(signatureGroup("")).toBe("Other");
  });
});

describe("signatureExtension", () => {
  it("maps fasta to .fasta", () => {
    expect(signatureExtension("fasta_map_protein")).toBe(".fasta");
    expect(signatureExtension("fasta_resname_nucleic")).toBe(".fasta");
  });

  it("maps smiles to .smi", () => {
    expect(signatureExtension("smiles")).toBe(".smi");
    expect(signatureExtension("smiles_not_sanitized")).toBe(".smi");
  });

  it("maps pdb variants to .pdb", () => {
    expect(signatureExtension("pdb_protein")).toBe(".pdb");
    expect(signatureExtension("pdb_nucleic")).toBe(".pdb");
    expect(signatureExtension("topology_less_pdb")).toBe(".pdb");
    expect(signatureExtension("ca_only_pdb")).toBe(".pdb");
  });

  it("maps mmcif to .cif", () => {
    expect(signatureExtension("mmcif")).toBe(".cif");
  });

  it("defaults to .txt", () => {
    expect(signatureExtension("morgan_fingerprint")).toBe(".txt");
    expect(signatureExtension("unknown")).toBe(".txt");
    expect(signatureExtension(null)).toBe(".txt");
  });
});
