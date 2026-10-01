import { describe, expect, it } from "vitest";
import { deriveInputFiles } from "./input-files";

describe("deriveInputFiles", () => {
  it("returns files under input/", () => {
    expect(deriveInputFiles(["input/top.gro", "input/system.tpr", "results.json"])).toEqual([
      "input/top.gro",
      "input/system.tpr",
    ]);
  });

  it("excludes nested directories beyond input/", () => {
    expect(
      deriveInputFiles(["input/sub/file.gro", "input/top.gro"]),
    ).toEqual(["input/top.gro"]);
  });

  it("excludes tmp*.json files", () => {
    expect(
      deriveInputFiles(["input/tmp123.json", "input/tmp_check.json", "input/top.gro"]),
    ).toEqual(["input/top.gro"]);
  });

  it("excludes files not under input/", () => {
    expect(deriveInputFiles(["results.json", "data.gro", "config.ini"])).toEqual([]);
  });

  it("handles empty list", () => {
    expect(deriveInputFiles([])).toEqual([]);
  });

  it("handles input/ prefix with no filename", () => {
    expect(deriveInputFiles(["input/"])).toEqual([]);
  });
});
