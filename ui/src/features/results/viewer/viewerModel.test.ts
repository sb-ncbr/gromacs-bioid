import { describe, expect, it } from "vitest";
import type { ViewModel } from "../viewmodel";
import { moleculeForChain, planScene, LIGHT_PALETTE } from "./viewerModel";
import navmsRaw from "../viewmodel/fixtures/navms-finished.json";
import largeRaw from "../viewmodel/fixtures/large-finished.json";

const navms = navmsRaw as unknown as ViewModel;
const large = largeRaw as unknown as ViewModel;
const chainA = navms.molecules[0];

describe("planScene · highlight mode (SPEC.md §3.5b)", () => {
  it("builds one component per kind present (A6 fix), water/ions hidden by default", () => {
    const plan = planScene(navms.molecules, "finished", "highlight", chainA.id, false);
    const builtins = plan.components.filter((c) => c.builtin).map((c) => c.key);
    expect(builtins).toContain("kind:protein");
    expect(builtins).not.toContain("kind:water");
    expect(builtins).not.toContain("kind:ion");
    // lipids share the neutral "other" non-standard component (G9 note)
    expect(builtins).toContain("kind:other");
  });

  it("adds the selected molecule's chain in accent + a matching legend", () => {
    const plan = planScene(navms.molecules, "finished", "highlight", chainA.id, false);
    const sel = plan.components.find((c) => c.key === `sel:${chainA.id}`)!;
    expect(sel.chainAsymId).toBe("A");
    expect(sel.representation).toBe("cartoon");
    expect(sel.colorHex).toBe(LIGHT_PALETTE.accent);
    expect(plan.legend.map((l) => l.label)).toEqual(["Chain A", "Other"]);
  });

  it("never highlights virtual segments (no chain → no selected component)", () => {
    const popc = navms.molecules.find((m) => m.display_name === "POPC")!;
    expect(popc.chain).toBeNull();
    const plan = planScene(navms.molecules, "finished", "highlight", popc.id, false);
    expect(plan.components.find((c) => c.key === `sel:${popc.id}`)).toBeUndefined();
    expect(plan.legend[0].label).toBe("Other");
  });

  it("shows water and ions with their legend when toggled", () => {
    const plan = planScene(navms.molecules, "finished", "highlight", chainA.id, true);
    expect(plan.components.map((c) => c.key)).toContain("kind:water");
    expect(plan.components.map((c) => c.key)).toContain("kind:ion");
    expect(plan.legend.map((l) => l.label)).toEqual(["Chain A", "Other", "Water", "Ions"]);
  });
});

describe("planScene · confidence mode (finished only)", () => {
  it("colours every chain-addressable molecule by its label", () => {
    const plan = planScene(navms.molecules, "finished", "confidence", null, false);
    const perMol = plan.components.filter((c) => c.key.startsWith("mol:"));
    // 4 chains (medium); POPC/POPX/SOD/… have no chain (G9)
    expect(perMol).toHaveLength(4);
    expect(perMol.every((c) => c.colorHex === LIGHT_PALETTE.medium)).toBe(true);
    expect(plan.legend.map((l) => l.label)).toEqual(["High", "Medium", "Low", "None"]);
  });

  it("colours not-identified chains in the None colour (SPEC.md §7)", () => {
    const unl = large.molecules.find((m) => m.result?.state === "not_identified")!;
    const plan = planScene(large.molecules, "finished", "confidence", null, false);
    if (unl.chain != null) {
      const comp = plan.components.find((c) => c.key === `mol:${unl.id}`)!;
      expect(comp.colorHex).toBe(LIGHT_PALETTE.none);
    } else {
      // virtual UNL: no selector, stays neutral — must NOT be coloured elsewhere
      expect(plan.components.find((c) => c.key === `mol:${unl.id}`)).toBeUndefined();
    }
  });

  it("falls back to highlight mode while the run is not finished", () => {
    const plan = planScene(navms.molecules, "running", "confidence", chainA.id, false);
    expect(plan.legend.map((l) => l.label)[0]).toBe("Chain A");
  });
});

describe("moleculeForChain (two-way selection, G9 note)", () => {
  it("maps a clicked chain back to the molecule id", () => {
    expect(moleculeForChain(navms.molecules, "A")).toBe(chainA.id);
    expect(moleculeForChain(navms.molecules, null)).toBeNull();
    expect(moleculeForChain(navms.molecules, "ZZZ")).toBeNull();
  });
});
