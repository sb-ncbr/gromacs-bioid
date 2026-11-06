import { describe, expect, it } from "vitest";
import type { Molecule, ViewModel } from "../viewmodel";
import { compositionLine, SYSTEM_SELECTION } from "./SystemStage";
import navmsRaw from "../viewmodel/fixtures/navms-finished.json";

const navms = navmsRaw as unknown as ViewModel;

const mol = (kind: Molecule["kind"], copies: number) =>
  ({ id: `${kind}${copies}`, kind, copies, atoms_per_copy: 1 }) as unknown as Molecule;

describe("whole-system view", () => {
  it("selection id cannot collide with a real segment named SYSTEM", () => {
    expect(SYSTEM_SELECTION).not.toBe("SYSTEM");
    expect(navms.molecules.some((m) => m.id === SYSTEM_SELECTION)).toBe(false);
  });

  it("composition counts copies by kind (3PTB shape)", () => {
    expect(compositionLine([mol("protein", 1), mol("small_molecule", 1), mol("ion", 1), mol("water", 62)]))
      .toBe("1 protein · 1 small molecule · 1 ion · 62 waters");
  });

  it("summarises a real fixture without empty parts", () => {
    const line = compositionLine(navms.molecules);
    expect(line.length).toBeGreaterThan(0);
    expect(line).not.toMatch(/undefined|NaN/);
  });
});
