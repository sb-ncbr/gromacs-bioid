import { describe, expect, it } from "vitest";
import {
  baseName,
  chainOf,
  clause,
  confLabel,
  elapsed,
  evidence,
  formatDb,
  formatInput,
  kindOf,
  stateOf,
  statusOf,
  stripSeg,
  type HitView,
} from "./derive";
import type { Stage } from "./types";

describe("stripSeg", () => {
  it("strips the seg_N_ prefix", () => {
    expect(stripSeg("seg_0_Protein_chain_A")).toBe("Protein_chain_A");
  });
  it("strips the __vN variant suffix", () => {
    expect(stripSeg("seg_12_POPC__v3")).toBe("POPC");
  });
  it("leaves plain names untouched", () => {
    expect(stripSeg("POPC")).toBe("POPC");
  });
});

describe("baseName / chainOf", () => {
  it("renders chains as Chain X", () => {
    expect(baseName("seg_0_Protein_chain_A")).toEqual({ name: "Chain A", chain: "A" });
    expect(chainOf("nucleic_chain_B")).toBe("B");
  });
  it("uses the residue/source name otherwise", () => {
    expect(baseName("seg_5_POPC")).toEqual({ name: "POPC", chain: null });
  });
});

describe("kindOf", () => {
  it("maps loader types to view kinds", () => {
    expect(kindOf("protein")).toBe("protein");
    expect(kindOf("lipid")).toBe("lipid");
    expect(kindOf("solvent")).toBe("water");
    expect(kindOf("carbohydrate")).toBe("small_molecule");
  });
  it("falls back to unknown (today's POPC quirk, gap G3 note)", () => {
    expect(kindOf("unknown")).toBe("unknown");
    expect(kindOf(null)).toBe("unknown");
  });
});

describe("formatDb / formatInput", () => {
  it("uses display labels, never raw enum names", () => {
    expect(formatDb("pubchem_cid")).toBe("PubChem");
    expect(formatDb("uniprot")).toBe("UniProt");
    expect(formatInput("gromacs")).toBe("GROMACS");
  });
  it("title-cases unknown databases instead of leaking ids", () => {
    expect(formatDb("foldseek")).toBe("Foldseek");
  });
});

describe("elapsed", () => {
  const start = "2026-10-26T10:00:00Z";
  const end = "2026-10-26T11:35:00Z";
  it("terminal runs use finished - started", () => {
    expect(elapsed("finished", start, end, Date.now())).toBe(5700);
  });
  it("running runs use now - started", () => {
    const now = Date.parse("2026-10-26T10:33:00Z");
    expect(elapsed("running", start, null, now)).toBe(1980);
  });
  it("queued runs have no elapsed time", () => {
    expect(elapsed("queued", null, null, Date.now())).toBeNull();
  });
});

describe("confLabel", () => {
  it("applies the spec thresholds exactly", () => {
    expect(confLabel(80)).toBe("high");
    expect(confLabel(79.9)).toBe("medium");
    expect(confLabel(50)).toBe("medium");
    expect(confLabel(49.9)).toBe("low");
  });
});

describe("stateOf", () => {
  it("marks ground-truth overrides and elements exact", () => {
    expect(stateOf({ ground_truth_override: "1IMO", is_verified: true }, true)).toBe("exact");
    expect(stateOf({ database: "element", is_verified: true }, true)).toBe("exact");
  });
  it("marks sub-50 confidence a lead", () => {
    expect(stateOf({ database: "pdb", final_confidence: 30, is_verified: true }, true)).toBe("lead");
  });
  it("no verified hits means not identified", () => {
    expect(stateOf(null, false)).toBe("not_identified");
  });
});

describe("evidence", () => {
  it("phrases sequence identity for sequence databases", () => {
    expect(evidence({ database: "pdb", similarity_score: 0.955 })).toBe("95.5% sequence identity");
    expect(evidence({ database: "uniprot", similarity_score: 87 })).toBe("87% sequence identity");
  });
  it("phrases structural and chemical matches per the copy deck", () => {
    expect(evidence({ database: "foldseek" })).toBe("same structure (stereo not compared)");
    expect(evidence({ database: "pubchem_cid", similarity_score: 1 })).toBe("same structure");
    expect(evidence({ database: "chembl", similarity_score: 0.4, skeleton_sim: 0.72 })).toBe(
      "similar skeleton (72%)",
    );
    expect(evidence({ database: "element" })).toBe("same element");
  });
});

describe("clause", () => {
  it("rewrites rejection reasons into short clauses (COPY.md §4)", () => {
    expect(clause("alignment identity below 30%")).toBe("sequence identity below 30%");
    expect(clause("structure RMSD too large")).toBe("structure does not match");
    expect(clause("different chemical formula")).toBe("different chemical formula");
    expect(clause("element mismatch")).toBe("different element");
    expect(clause("verification worker failed")).toBe("could not be checked");
    expect(clause(null)).toBe("did not pass verification");
  });
});

describe("statusOf (G2 fallback)", () => {
  const stage = (status: Stage["status"]): Stage => ({
    key: "search",
    label: "Search databases",
    status,
    duration_s: null,
  });
  it("follows the run and search-stage state", () => {
    expect(statusOf("finished", stage("done"))).toBe("done");
    expect(statusOf("running", stage("waiting"))).toBe("waiting");
    expect(statusOf("running", stage("active"))).toBe("searching");
    expect(statusOf("running", stage("done"))).toBe("searched");
    expect(statusOf("failed", stage("done"))).toBe("searched");
    expect(statusOf("failed", stage("failed"))).toBe("not_searched");
  });
});

describe("HitView structural typing", () => {
  it("accepts additive G5 fields the generated baseline lacks", () => {
    const hit: HitView = { identifier: "5HVX", name: "Lysosome", organism: "Homo sapiens" };
    expect(hit.name).toBe("Lysosome");
  });
});
