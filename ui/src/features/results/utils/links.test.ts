import { describe, expect, it } from "vitest";
import { buildDatabaseUrl, ensureChemblPrefix, fixDatabaseUrl, resolveHitUrl, stripPdbChain } from "./links";

describe("stripPdbChain", () => {
  it("strips _CHAIN suffix", () => {
    expect(stripPdbChain("1ABC_A")).toBe("1ABC");
    expect(stripPdbChain("1ABC_B")).toBe("1ABC");
  });

  it("returns unchanged if no underscore", () => {
    expect(stripPdbChain("1ABC")).toBe("1ABC");
  });
});

describe("ensureChemblPrefix", () => {
  it("adds CHEMBL prefix to bare id", () => {
    expect(ensureChemblPrefix("4303682")).toBe("CHEMBL4303682");
  });

  it("preserves existing CHEMBL prefix", () => {
    expect(ensureChemblPrefix("CHEMBL4303682")).toBe("CHEMBL4303682");
  });

  it("handles lowercase input", () => {
    expect(ensureChemblPrefix("chembl123")).toBe("CHEMBL123");
  });
});

describe("buildDatabaseUrl", () => {
  it("builds PDB URL and strips _CHAIN", () => {
    expect(buildDatabaseUrl("PDB_ID", "1ABC_A")).toBe("https://www.rcsb.org/structure/1ABC");
    expect(buildDatabaseUrl("PDB_ID", "2XYZ")).toBe("https://www.rcsb.org/structure/2XYZ");
  });

  it("builds UniProt URL", () => {
    expect(buildDatabaseUrl("UNIPROT_ID", "P12345")).toBe("https://www.uniprot.org/uniprotkb/P12345");
  });

  it("builds ChEMBL URL with prefix", () => {
    expect(buildDatabaseUrl("CHEMBL_ID", "4303682")).toBe(
      "https://www.ebi.ac.uk/chembl/explore/compound/CHEMBL4303682",
    );
    expect(buildDatabaseUrl("CHEMBL_ID", "CHEMBL4303682")).toBe(
      "https://www.ebi.ac.uk/chembl/explore/compound/CHEMBL4303682",
    );
  });

  it("builds ChEBI URL", () => {
    expect(buildDatabaseUrl("CHEBI_ID", "15377")).toBe(
      "https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:15377",
    );
  });

  it("builds AlphaFold URL", () => {
    expect(buildDatabaseUrl("ALPHAFOLD_ID", "A0")).toBe("https://alphafold.ebi.ac.uk/entry/A0");
  });

  it("builds PubChem URL", () => {
    expect(buildDatabaseUrl("PUBCHEM_CID", "12345")).toBe(
      "https://pubchem.ncbi.nlm.nih.gov/compound/12345",
    );
  });

  it("builds CCD URL", () => {
    expect(buildDatabaseUrl("CCD_ID", "LIG")).toBe("https://www.wwpdb.org/data/ccd/LIG");
  });

  it("builds AlphaFind URL", () => {
    expect(buildDatabaseUrl("ALPHAFIND_ID", "abc123")).toBe("https://alphafind.fi.muni.cz/abc123");
  });

  it("returns null for unknown ident_type", () => {
    expect(buildDatabaseUrl("UNKNOWN_TYPE", "foo")).toBeNull();
  });

  it("returns null for empty identifier", () => {
    expect(buildDatabaseUrl("PDB_ID", "")).toBeNull();
    expect(buildDatabaseUrl("PDB_ID", null)).toBeNull();
  });
});

describe("fixDatabaseUrl", () => {
  it("strips _CHAIN from rcsb URLs", () => {
    expect(fixDatabaseUrl("https://www.rcsb.org/structure/1ABC_A")).toBe(
      "https://www.rcsb.org/structure/1ABC",
    );
  });

  it("adds CHEMBL prefix to bare numeric chembl URLs", () => {
    expect(fixDatabaseUrl("https://www.ebi.ac.uk/chembl/explore/compound/4303682")).toBe(
      "https://www.ebi.ac.uk/chembl/explore/compound/CHEMBL4303682",
    );
  });

  it("leaves valid URLs unchanged", () => {
    expect(fixDatabaseUrl("https://www.rcsb.org/structure/1ABC")).toBe(
      "https://www.rcsb.org/structure/1ABC",
    );
    expect(fixDatabaseUrl("https://www.ebi.ac.uk/chembl/explore/compound/CHEMBL123")).toBe(
      "https://www.ebi.ac.uk/chembl/explore/compound/CHEMBL123",
    );
  });
});

describe("resolveHitUrl", () => {
  it("prefers built URL over database_url", () => {
    const url = resolveHitUrl({
      identifier: "1ABC_A",
      ident_type: "PDB_ID",
      database_url: "https://wrong.example.com",
    });
    expect(url).toBe("https://www.rcsb.org/structure/1ABC");
  });

  it("falls back to database_url when ident_type is unknown", () => {
    const url = resolveHitUrl({
      identifier: "foo",
      ident_type: "UNKNOWN",
      database_url: "https://example.com/foo",
    });
    expect(url).toBe("https://example.com/foo");
  });

  it("returns null when no info available", () => {
    expect(resolveHitUrl({ identifier: "", ident_type: null, database_url: null })).toBeNull();
  });
});
