import { describe, expect, it } from "vitest";
import { splitRunName } from "./runName";

describe("splitRunName", () => {
  it("splits title and description at the first >", () => {
    expect(splitRunName("Trypsin>Crystal structure > PDB 3PTB")).toEqual({
      title: "Trypsin",
      description: "Crystal structure > PDB 3PTB",
    });
  });
  it("keeps plain names whole", () => {
    expect(splitRunName("MDR00042100 (re-run)")).toEqual({ title: "MDR00042100 (re-run)", description: null });
    expect(splitRunName(null)).toEqual({ title: "", description: null });
    expect(splitRunName("Name>")).toEqual({ title: "Name", description: null });
  });
});
