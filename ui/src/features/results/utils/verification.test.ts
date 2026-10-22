import { describe, expect, it } from "vitest";
import { bestConfidence, presentHits, verifiedOnlyHits, truncateName, type VerifiedHit,
  confidenceBreakdown,
  groupByClass,
} from "./verification";

function makeHit(overrides: Partial<VerifiedHit>): VerifiedHit {
  return {
    identifier: "1ABC",
    ident_type: "PDB_ID",
    database: "pdb",
    final_confidence: 90,
    is_verified: true,
    supporting_evidence_count: 0,
    ...overrides,
  };
}

describe("presentHits", () => {
  it("preserves input order exactly (no re-sort)", () => {
    const hits: VerifiedHit[] = [
      makeHit({ identifier: "Z", final_confidence: 50 }),
      makeHit({ identifier: "A", final_confidence: 99 }),
      makeHit({ identifier: "M", final_confidence: 75 }),
    ];
    const result = presentHits(hits);
    expect(result.map((h) => h.identifier)).toEqual(["Z", "A", "M"]);
  });

  it("returns empty array for null/undefined", () => {
    expect(presentHits(null)).toEqual([]);
    expect(presentHits(undefined)).toEqual([]);
  });

  it("returns a copy (not same reference)", () => {
    const hits: VerifiedHit[] = [makeHit({})];
    const result = presentHits(hits);
    expect(result).not.toBe(hits);
    expect(result).toEqual(hits);
  });
});

describe("verifiedOnlyHits", () => {
  it("keeps verified hits only, preserving stored order (filtering != sorting)", () => {
    const hits: VerifiedHit[] = [
      makeHit({ identifier: "Z", is_verified: true }),
      makeHit({ identifier: "A", is_verified: false }),
      makeHit({ identifier: "M", is_verified: true }),
    ];
    expect(verifiedOnlyHits(hits).map((h) => h.identifier)).toEqual(["Z", "M"]);
  });

  it("SOD shape (run b4813beb): single verified ELEMENT among rejected rows -> one row", () => {
    const hits: VerifiedHit[] = [
      ...Array.from({ length: 3 }, (_, i) =>
        makeHit({ identifier: `REJ_${i}`, is_verified: false, rejection_reason: "fingerprint_unavailable" })),
      makeHit({ identifier: "NA", ident_type: "ELEMENT", is_verified: true, final_confidence: 100 }),
    ];
    const out = verifiedOnlyHits(hits);
    expect(out).toHaveLength(1);
    expect(out[0].identifier).toBe("NA");
  });

  it("empty state: no verified rows -> empty list (panel shows failed-to-identify copy)", () => {
    const hits: VerifiedHit[] = [makeHit({ is_verified: false }), makeHit({ is_verified: false })];
    expect(verifiedOnlyHits(hits)).toEqual([]);
  });

  it("null/undefined -> empty list", () => {
    expect(verifiedOnlyHits(null)).toEqual([]);
    expect(verifiedOnlyHits(undefined)).toEqual([]);
  });
});

describe("bestConfidence", () => {
  it("returns final_confidence of first hit", () => {
    const hits = [
      makeHit({ final_confidence: 87.5 }),
      makeHit({ final_confidence: 99 }),
    ];
    expect(bestConfidence(hits)).toBe(87.5);
  });

  it("returns null when the top hit carries no informative confidence (v3.140 plateau)", () => {
    // backend nulls final_confidence when the value is the deterministic
    // family plateau (skel==1.0 + resolver capped) — the panel must render
    // "—", not a fabricated 0%
    const hits = [
      makeHit({ final_confidence: null }),
      makeHit({ final_confidence: 99 }),
    ];
    expect(bestConfidence(hits)).toBeNull();
  });

  it("returns 0 for empty array", () => {
    expect(bestConfidence([])).toBe(0);
  });

  it("returns 0 for null/undefined", () => {
    expect(bestConfidence(null)).toBe(0);
    expect(bestConfidence(undefined)).toBe(0);
  });
});

describe("truncateName", () => {
  it("returns short names unchanged", () => {
    expect(truncateName("short")).toBe("short");
    expect(truncateName("")).toBe("");
  });

  it("truncates names longer than 60 chars with ellipsis", () => {
    const long = "A".repeat(80);
    const result = truncateName(long);
    expect(result.length).toBe(60);
    expect(result.endsWith("\u2026")).toBe(true);
    expect(result.slice(0, 59)).toBe("A".repeat(59));
  });

  it("respects custom max length", () => {
    const result = truncateName("Hello, World!", 8);
    expect(result).toBe("Hello, \u2026");
    expect(result.length).toBe(8);
  });

  it("handles null/undefined", () => {
    expect(truncateName(null)).toBe("");
    expect(truncateName(undefined)).toBe("");
  });
});

describe("confidenceBreakdown", () => {
  it("renders all non-null terms with one decimal, omitting unknowns", () => {
    const h: VerifiedHit = {
      identifier: "311", ident_type: "PUBCHEM_CID", database: "pubchem",
      final_confidence: 63.6, belief: 60.4, similarity_score: 62.9,
      annotation_quality_score: 70, skeleton_sim: 1.0, is_verified: true,
    };
    expect(confidenceBreakdown(h)).toBe(
      "belief 60.4 \u00b7 match 62.9 \u00b7 annotation 70.0 \u00b7 skeleton 1.0",
    );
  });
  it("returns empty string for fully legacy rows", () => {
    const h: VerifiedHit = {
      identifier: "1ABC", ident_type: "PDB_ID", database: "pdb",
      final_confidence: 88.0, is_verified: true,
    };
    expect(confidenceBreakdown(h)).toBe("");
  });
});

describe("groupByClass", () => {
  const mk = (identifier: string, cls: string | null): VerifiedHit => ({
    identifier, ident_type: "PUBCHEM_CID", database: "pubchem",
    final_confidence: 60, is_verified: true, equivalence_class_id: cls,
  });
  it("groups by class id preserving stored order, primary first", () => {
    const rows = [mk("A", "skeleton:x"), mk("B", "skeleton:x"), mk("C", "align:0.9"), mk("D", "skeleton:x")];
    const groups = groupByClass(rows);
    expect(groups).toHaveLength(2);
    expect(groups[0].primary.identifier).toBe("A");
    expect(groups[0].members.map((h) => h.identifier)).toEqual(["A", "B", "D"]);
    expect(groups[1].members.map((h) => h.identifier)).toEqual(["C"]);
  });
  it("legacy rows without class id never merge", () => {
    const groups = groupByClass([mk("A", null), mk("B", null)]);
    expect(groups).toHaveLength(2);
    expect(groups.every((g) => g.members.length === 1)).toBe(true);
  });
  it("handles null/undefined input", () => {
    expect(groupByClass(null)).toEqual([]);
    expect(groupByClass(undefined)).toEqual([]);
  });
});
