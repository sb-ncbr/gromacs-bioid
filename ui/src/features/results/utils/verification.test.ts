import { describe, expect, it } from "vitest";
import { bestConfidence, presentHits, truncateName, type VerifiedHit } from "./verification";

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

describe("bestConfidence", () => {
  it("returns final_confidence of first hit", () => {
    const hits = [
      makeHit({ final_confidence: 87.5 }),
      makeHit({ final_confidence: 99 }),
    ];
    expect(bestConfidence(hits)).toBe(87.5);
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
