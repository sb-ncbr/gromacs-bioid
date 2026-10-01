import { describe, expect, it } from "vitest";
import { buildDownloadBlob, exportFilename, hitsToJson, hitsToTsv } from "./export";
import type { VerifiedHit } from "./verification";

const sampleHits: VerifiedHit[] = [
  {
    identifier: "1ABC",
    ident_type: "PDB_ID",
    database: "pdb",
    final_confidence: 95.2,
    is_verified: true,
    rejection_reason: null,
    supporting_evidence_count: 2,
    database_url: "https://www.rcsb.org/structure/1ABC",
  },
  {
    identifier: "CHEMBL123",
    ident_type: "CHEMBL_ID",
    database: "chembl",
    final_confidence: 80.1,
    is_verified: false,
    rejection_reason: "low similarity",
    supporting_evidence_count: 0,
    database_url: null,
  },
];

describe("hitsToTsv", () => {
  it("produces header + rows", () => {
    const tsv = hitsToTsv(sampleHits);
    const lines = tsv.trimEnd().split("\n");
    expect(lines[0]).toBe(
      "identifier\tident_type\tdatabase\tresolver_score\tsimilarity_score\tannotation_quality_score\tfinal_confidence\tis_verified\trejection_reason\tsupporting_evidence_count\tdatabase_url",
    );
    expect(lines).toHaveLength(3); // header + 2 rows
    expect(lines[1]).toContain("1ABC");
    expect(lines[1]).toContain("95.2");
    expect(lines[2]).toContain("CHEMBL123");
  });

  it("returns header + newline for empty hits", () => {
    const tsv = hitsToTsv([]);
    expect(tsv).toBe(
      "identifier\tident_type\tdatabase\tresolver_score\tsimilarity_score\tannotation_quality_score\tfinal_confidence\tis_verified\trejection_reason\tsupporting_evidence_count\tdatabase_url\n",
    );
  });

  it("escapes tabs and newlines in values", () => {
    const hits: VerifiedHit[] = [
      {
        identifier: "has\ttab",
        ident_type: "PDB_ID",
        database: "pdb",
        final_confidence: 50,
        is_verified: true,
        supporting_evidence_count: 0,
      },
    ];
    const tsv = hitsToTsv(hits);
    expect(tsv).toContain('"has\ttab"');
  });

  it("returns header-only for null/undefined", () => {
    expect(hitsToTsv(null).trimEnd().split("\n")).toHaveLength(1);
    expect(hitsToTsv(undefined).trimEnd().split("\n")).toHaveLength(1);
  });
});

describe("hitsToJson", () => {
  it("produces valid JSON array", () => {
    const json = hitsToJson(sampleHits);
    const parsed = JSON.parse(json);
    expect(Array.isArray(parsed)).toBe(true);
    expect(parsed).toHaveLength(2);
    expect(parsed[0].identifier).toBe("1ABC");
    expect(parsed[1].is_verified).toBe(false);
  });

  it("returns empty array for empty hits", () => {
    expect(JSON.parse(hitsToJson([]))).toEqual([]);
  });

  it("returns empty array for null/undefined", () => {
    expect(JSON.parse(hitsToJson(null))).toEqual([]);
    expect(JSON.parse(hitsToJson(undefined))).toEqual([]);
  });
});

describe("buildDownloadBlob", () => {
  it("creates a blob with correct type and content", () => {
    const blob = buildDownloadBlob("hello", "text/plain");
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.type).toBe("text/plain");
    expect(blob.size).toBe(5);
  });
});

describe("exportFilename", () => {
  it("sanitizes the segment name", () => {
    expect(exportFilename("seg_0_PROA", "tsv")).toBe("seg_0_PROA.tsv");
    expect(exportFilename("seg/0 PROA", "json")).toBe("seg_0_PROA.json");
  });

  it("defaults to 'verification' when empty", () => {
    expect(exportFilename("", "tsv")).toBe("verification.tsv");
  });
});
