import { describe, expect, it } from "vitest";
import { MVSData } from "molstar/lib/extensions/mvs/mvs-data";
import type { ViewModel } from "../viewmodel";
import { buildMvs } from "./mvsScene";
import { planScene } from "./viewerModel";
import navmsRaw from "../viewmodel/fixtures/navms-finished.json";
import largeRaw from "../viewmodel/fixtures/large-finished.json";

const fixtures = { navms: navmsRaw, large: largeRaw } as unknown as Record<string, ViewModel>;

describe("buildMvs · every scene passes Mol* MVS validation", () => {
  for (const [name, vm] of Object.entries(fixtures)) {
    for (const mode of ["highlight", "confidence"] as const) {
      for (const water of [false, true]) {
        it(`${name} · ${mode} · water/ions ${water ? "on" : "off"}`, () => {
          const sel = vm.molecules[0]?.id ?? null;
          const plan = planScene(vm.molecules, "finished", mode, sel, water);
          const state = buildMvs("https://example.org/system.mmcif", plan.components);
          expect(MVSData.validationIssues(state, { noExtra: true })).toBeUndefined();
        });
      }
    }
  }
});

describe("buildMvs · G9 selector components validate too", () => {
  it("atom-index and selector-chain components pass MVS validation", () => {
    const state = buildMvs("https://example.org/system.mmcif", [
      { key: "a", chainAsymId: "PROA", representation: "cartoon", colorHex: "#1f5f26" },
      { key: "b", atomIndices: [1629, 1630, 1631], representation: "ball_and_stick", colorHex: "#9a3412" },
    ]);
    expect(MVSData.validationIssues(state, { noExtra: true })).toBeUndefined();
  });
});

describe("buildMvs · residue-range components validate", () => {
  it("auth_seq_id range components pass MVS validation", () => {
    const state = buildMvs("https://example.org/system.mmcif", [
      { key: "w", residueRanges: [["A", 301, 362], ["B", 1, 1]], representation: "ball_and_stick", colorHex: "#1f5f26" },
    ]);
    expect(MVSData.validationIssues(state, { noExtra: true })).toBeUndefined();
  });
});
