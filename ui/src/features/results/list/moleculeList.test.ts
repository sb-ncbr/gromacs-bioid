import { describe, expect, it } from "vitest";
import type { Molecule, ViewModel } from "../viewmodel";
import {
  applyQuery,
  bucketOf,
  counts,
  defaultSelection,
  identGroups,
  kindGroups,
  loadCollapsed,
  matches,
  rowOf,
  saveCollapsed,
} from "./moleculeList";
import navmsFinishedRaw from "../viewmodel/fixtures/navms-finished.json";
import navmsRunningRaw from "../viewmodel/fixtures/navms-running.json";
import navmsFailedRaw from "../viewmodel/fixtures/navms-failed.json";
import largeFinishedRaw from "../viewmodel/fixtures/large-finished.json";

const navms = navmsFinishedRaw as unknown as ViewModel;
const navmsRunning = navmsRunningRaw as unknown as ViewModel;
const navmsFailed = navmsFailedRaw as unknown as ViewModel;
const large = largeFinishedRaw as unknown as ViewModel;

const mol = (over: Partial<Molecule>): Molecule => ({
  id: "seg_0_X",
  display_name: "X",
  kind: "protein",
  chain: null,
  residue_names: [],
  copies: 1,
  atoms_per_copy: 1,
  residues_per_copy: null,
  status: "done",
  result: null,
  matches: [],
  more: { verified: 0, related: 0, rejected: 0 },
  descriptor: {},
  note_ids: [],
  ...over,
});

describe("bucketing (SPEC.md §3.4, §4)", () => {
  it("counts Exact under High for the distribution", () => {
    const out = counts(navms.molecules, "finished");
    expect(out.high).toBe(6); // SOD, PORE_ION, CLA (exact) + POPX, POPC, SOL (94)
    expect(out.medium).toBe(4); // the 78-confidence chains A–D
    expect(out.low ?? 0).toBe(0);
    expect(out.none ?? 0).toBe(0);
  });

  it("uses live buckets while running: 6 searched · 1 searching · 3 waiting", () => {
    const out = counts(navmsRunning.molecules, "running");
    expect(out.searched).toBe(6);
    expect(out.searching).toBe(1);
    expect(out.waiting).toBe(3);
  });

  it("splits failed runs into searched / not searched", () => {
    const out = counts(navmsFailed.molecules, "failed");
    expect(out.searched + (out.not_searched ?? 0)).toBe(10);
    expect(out.not_searched).toBeGreaterThan(0);
  });

  it("lead and not-identified land in low / none", () => {
    const out = counts(large.molecules, "finished");
    expect(out.low).toBe(large.molecules.filter((m) => m.result?.state === "lead").length);
    expect(out.none).toBe(large.molecules.filter((m) => m.result?.state === "not_identified").length);
  });
});

describe("filter + search", () => {
  it("the None key shows only not-identified rows (SPEC.md §7)", () => {
    const out = applyQuery(large.molecules, "none", "", "finished");
    expect(out.length).toBeGreaterThan(0);
    expect(out.every((m) => m.result?.state === "not_identified")).toBe(true);
  });

  it("search 'po' on the large fixture finds POPC, POPE, POPS and POT (SPEC.md §7)", () => {
    const out = applyQuery(large.molecules, null, "po", "finished");
    const names = out.map((m) => m.display_name);
    expect(names).toContain("POPC");
    expect(names).toContain("POPE");
    expect(names).toContain("POPS");
    expect(names).toContain("POT");
    expect(out).toHaveLength(4);
  });

  it("matches chain wording and ignores case", () => {
    const m = mol({ display_name: "Chain A", chain: "A" });
    expect(matches(m, "chain a")).toBe(true);
    expect(matches(m, "CHAIN A")).toBe(true);
    expect(matches(m, "zzz")).toBe(false);
  });
});

describe("kind grouping (SPEC.md §3.4)", () => {
  it("groups the NavMs fixture by kind, keeping file order inside groups", () => {
    const groups = kindGroups(navms.molecules, "finished");
    expect(groups.map((g) => g.key)).toEqual(["protein", "lipid", "ion", "water"]);
    expect(groups.find((g) => g.key === "protein")!.rows.map((r) => r.molecule.display_name)).toEqual([
      "Chain A",
      "Chain B",
      "Chain C",
      "Chain D",
    ]);
  });

  it("starts ions and water collapsed with their copy counts", () => {
    const groups = kindGroups(navms.molecules, "finished");
    expect(groups.find((g) => g.key === "ion")!.defaultCollapsed).toBe(true);
    expect(groups.find((g) => g.key === "water")!.defaultCollapsed).toBe(true);
    expect(groups.find((g) => g.key === "protein")!.defaultCollapsed).toBe(false);
  });

  it("renders row scores as rounded numbers with exact rows having none", () => {
    const groups = kindGroups(navms.molecules, "finished");
    const chainA = groups[0].rows[0];
    expect(chainA.score).toBe(78);
    const sod = groups.find((g) => g.key === "ion")!.rows.find((r) => r.icon === "exact")!;
    expect(sod.score).toBeNull();
    expect(sod.hint).toBe("Exact match");
  });
});

describe("identification grouping (SPEC.md §3.4, finished only)", () => {
  it("merges the NavMs fixture into exactly 5 rows (SPEC.md §7)", () => {
    const rows = identGroups(navms.molecules);
    expect(rows).toHaveLength(5);
    const byCount = rows.map((r) => r.count).sort((a, b) => a - b);
    expect(byCount).toEqual([1, 1, 2, 2, 4]);
  });

  it("keeps not-identified molecules as singleton rows", () => {
    const rows = identGroups(large.molecules);
    const singletons = rows.filter((r) => r.memberIds.length === 1 && r.icon === "none");
    const notIdentified = large.molecules.filter((m) => m.result?.state === "not_identified");
    expect(singletons.length).toBe(notIdentified.length);
  });

  it("sorts least certain first", () => {
    const rows = identGroups(navms.molecules);
    const scores = rows.map((r) => r.score ?? -1);
    const sorted = [...scores].sort((a, b) => a - b);
    expect(scores).toEqual(sorted);
  });

  it("groups identical chains under their shared name", () => {
    const rows = identGroups(navms.molecules);
    const chains = rows.find((r) => r.memberIds.length === 4)!;
    expect(chains.memberLabels).toEqual(["Chain A", "Chain B", "Chain C", "Chain D"]);
    expect(chains.score).toBe(78);
  });
});

describe("default selection (SPEC.md §3.4)", () => {
  it("selects the first molecule that is not an ion or water", () => {
    expect(defaultSelection(navms.molecules)).toBe(navms.molecules[0].id);
  });
  it("prefers the first identified molecule over an unidentified fragment", () => {
    const miss = mol({ id: "frag", kind: "protein", result: { state: "not_identified", name: null, description: null, best: null, confidence: null } });
    const hit = mol({ id: "rec", kind: "protein", result: { state: "identified", name: "Receptor", description: null, best: null, confidence: 84 } });
    expect(defaultSelection([miss, hit])).toBe("rec");
    expect(defaultSelection([miss])).toBe("frag");
  });
  it("falls back to the first row when all are ions/water", () => {
    const ions = [mol({ id: "i1", kind: "ion" }), mol({ id: "w1", kind: "water" })];
    expect(defaultSelection(ions)).toBe("i1");
    expect(defaultSelection([])).toBeNull();
  });
});

describe("row line 2 while live (COPY.md §2.3)", () => {
  const running = mol({ id: "r", status: "searching" });
  it("phrases per-molecule status", () => {
    expect(rowOf(mol({ status: "waiting" }), "running").line2).toBe("Waiting");
    expect(rowOf(running, "running").line2).toBe("Searching databases…");
    expect(rowOf(mol({ status: "searched" }), "running").line2).toBe("Searched, waiting for checks");
    expect(rowOf(mol({ status: "searched" }), "failed").line2).toBe("Searched, not checked");
    expect(rowOf(mol({ status: "not_searched" }), "failed").line2).toBe("Not searched");
  });
});

describe("row text when identified (SPEC.md §3.4)", () => {
  it("shows the identified name; falls back to the description when name == label", () => {
    const popc = navms.molecules.find((m) => m.display_name === "POPC")!;
    const row = rowOf(popc, "finished");
    // name repeats the label → the description takes over
    expect(row.line2.length).toBeGreaterThan(0);
    expect(row.line2).not.toBe("Not identified");
  });
  it("marks misses explicitly", () => {
    const unl = large.molecules.find((m) => m.result?.state === "not_identified")!;
    expect(rowOf(unl, "finished").line2).toBe("Not identified");
    expect(rowOf(unl, "finished").hint).toBe("Not identified");
  });
});

describe("collapsed-group persistence", () => {
  it("round-trips through the injected storage", () => {
    const mem = new Map<string, string>();
    const storage: Storage = {
      getItem: (k) => mem.get(k) ?? null,
      setItem: (k, v) => void mem.set(k, v),
      removeItem: (k) => void mem.delete(k),
      clear: () => mem.clear(),
      key: () => null,
      length: mem.size,
    };
    saveCollapsed(storage, "run1", new Set(["ion", "water"]));
    expect(loadCollapsed(storage, "run1")).toEqual(new Set(["ion", "water"]));
    expect(loadCollapsed(storage, "other")).toEqual(new Set());
  });
  it("tolerates unavailable storage", () => {
    expect(loadCollapsed(null, "run1")).toEqual(new Set());
    expect(() => saveCollapsed(null, "run1", new Set(["ion"]))).not.toThrow();
  });
});

describe("bucketOf finished edge cases", () => {
  it("identified without confidence falls to none (defensive)", () => {
    const m = mol({ result: { state: "identified", name: null, description: null, best: null, confidence: null } });
    expect(bucketOf(m, "finished")).toBe("none");
  });
  it("pill colours never carry meaning alone: every bucket has a distinct icon", () => {
    const mel = mol({ result: { state: "exact", name: null, description: null, best: null, confidence: null } });
    expect(rowOf(mel, "finished").icon).toBe("exact");
  });
});
