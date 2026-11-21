import { describe, expect, it } from "vitest";
import { completenessHint, completenessOf, completenessSuffix } from "./runCompleteness";

describe("runCompleteness (2026-11-21, mdval audit item 7)", () => {
  it("accepts only the three values", () => {
    expect(completenessOf("partial")).toBe("partial");
    expect(completenessOf("bogus")).toBeNull();
    expect(completenessOf(null)).toBeNull();
    expect(completenessSuffix("complete")).toBeNull();
    expect(completenessSuffix("incomplete")).toBe("incomplete");
  });

  it("names the stages that ran out of time", () => {
    expect(completenessHint("partial", ["identify_molecules", "verify_results"])).toBe(
      "Finished, but the database search, checking the matches ran out of time: molecules handled after the limit may have fewer matches or none.",
    );
    expect(completenessHint("partial", [])).toMatch(/^Finished, but a stage ran out of time/);
    expect(completenessHint("incomplete", [])).toMatch(/database lookups failed/);
    expect(completenessHint("complete", ["x"])).toBeNull();
  });
});
