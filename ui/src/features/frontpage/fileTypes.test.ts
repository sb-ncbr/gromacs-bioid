import { describe, expect, it } from "vitest";
import { inputHints, isAccepted } from "./fileTypes";

describe("isAccepted", () => {
  it("takes simulation formats and bundles, not other text files", () => {
    expect(isAccepted("topol.tpr")).toBe(true);
    expect(isAccepted("SYSTEM.PDB")).toBe(true);
    expect(isAccepted("inputs.tar.gz")).toBe(true);
    expect(isAccepted("notes.txt")).toBe(false);
    expect(isAccepted("README")).toBe(false);
  });
});

describe("inputHints", () => {
  it("is quiet for complete inputs", () => {
    expect(inputHints(["topol.tpr"])).toEqual([]);
    expect(inputHints(["topol.top", "conf.gro", "lig.itp"])).toEqual([]);
    expect(inputHints(["sys.prmtop", "sys.rst7"])).toEqual([]);
    expect(inputHints(["sim.zip"])).toEqual(["Archives are not unpacked: upload the files inside them."]);
  });
  it("names the missing half", () => {
    expect(inputHints(["topol.top"])[0]).toMatch(/\.gro/);
    expect(inputHints(["sys.prmtop"])[0]).toMatch(/\.rst7/);
    expect(inputHints(["step5.psf"])[0]).toMatch(/\.pdb/);
    expect(inputHints(["traj.xtc"])[0]).toMatch(/\.tpr/);
  });
});

describe("what the server accepts (2026-11-17)", () => {
  it("accepts .ent and the auxiliaries", () => {
    for (const n of ["x.ent", "index.ndx", "md.mdp", "par.prm", "top.rtf", "toppar.str", "step.inp"]) {
      expect(isAccepted(n)).toBe(true);
    }
  });
  it("warns, but does not stop, a .gro without a topology", () => {
    expect(inputHints(["conf.gro"])[0]).toContain("likely be incomplete");
    expect(inputHints(["conf.gro", "topol.top"])).toEqual([]);
    expect(inputHints(["s.psf", "s.cif"])[0]).toContain("A .psf needs coordinates");
  });
});
