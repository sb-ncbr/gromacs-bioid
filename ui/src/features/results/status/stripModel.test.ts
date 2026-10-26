import { describe, expect, it } from "vitest";
import type { Molecule, Note, Stage, ViewModel } from "../viewmodel";
import { activeStepIndex, affectsNames, factsLine, humanDuration, notesPill } from "./stripModel";
import navmsFinishedRaw from "../viewmodel/fixtures/navms-finished.json";
import navmsRunningRaw from "../viewmodel/fixtures/navms-running.json";

const finished = navmsFinishedRaw as unknown as ViewModel;
const running = navmsRunningRaw as unknown as ViewModel;

const stage = (over: Partial<Stage>): Stage => ({
  key: "read",
  label: "Read files",
  status: "done",
  duration_s: null,
  ...over,
} as Stage);

describe("humanDuration", () => {
  it("seconds, minutes, hours", () => {
    expect(humanDuration(42)).toBe("42 s");
    expect(humanDuration(59)).toBe("59 s");
    expect(humanDuration(60)).toBe("1 min");
    expect(humanDuration(60 * 9 + 30)).toBe("9 min");
    expect(humanDuration(3600)).toBe("1 h");
    expect(humanDuration(3600 + 5 * 60)).toBe("1 h 5 min");
  });
});

describe("factsLine", () => {
  it("finished: sums step durations", () => {
    const stages: Stage[] = [stage({ duration_s: 100 }), stage({ label: "Find molecules", status: "done", duration_s: 134 })];
    expect(factsLine("finished", stages)).toBe("Finished in 3 min");
    expect(factsLine("finished", [stage({ label: "Read files" })])).toBe("Finished");
  });
  it("running: points at the current step with elapsed time", () => {
    const stages: Stage[] = [stage({}), stage({ label: "Find molecules" }), stage({ label: "Describe molecules", status: "active", duration_s: 132 })];
    expect(factsLine("running", stages)).toBe("Step 3 of 3 · Describe molecules · 2 min");
    expect(factsLine("running", [stage({ status: "waiting" })])).toBe("Working…");
  });
  it("queued and failed wording", () => {
    expect(factsLine("queued", [])).toContain("Waiting for a free worker");
    const stages = [stage({}), stage({ label: "Search databases", status: "failed" })];
    expect(factsLine("failed", stages, "Something broke")).toBe("Stopped at Search databases — Something broke");
    expect(factsLine("failed", [stage({})])).toBeNull();
  });
  it("activeStepIndex finds the running step (navms-running: search is active)", () => {
    const i = activeStepIndex(running.progress.stages);
    expect(running.progress.stages[i].label).toBe("Search databases");
    expect(activeStepIndex(finished.progress.stages)).toBe(-1);
  });
});

describe("notesPill", () => {
  const note = (severity: Note["severity"]): Note => ({
    id: "n", severity, code: "c", title: "t", body: "b", action: null, affects: [], raw_count: 1,
  });
  it("is null with no notes and counts severity otherwise", () => {
    expect(notesPill([])).toBeNull();
    expect(notesPill([note("info")])).toEqual({ total: 1, attention: 0, label: "1 note", needsAttention: false });
    expect(notesPill([note("attention"), note("info"), note("attention")])!.label).toBe("3 notes");
    expect(notesPill([note("attention"), note("info")])!.needsAttention).toBe(true);
  });
});

describe("affectsNames (G4: chips hide until backend lands)", () => {
  const mol = (id: string, display_name: string): Molecule => ({ id, display_name }) as Molecule;
  it("maps known segment ids to display names, drops unknowns", () => {
    const n = {
      id: "n", severity: "info", code: "c", title: "t", body: "b", action: null,
      affects: ["seg_a", "seg_unknown", "seg_b"], raw_count: 1,
    } as Note;
    const molecules = [mol("seg_a", "Chain A"), mol("seg_b", "POPC")];
    expect(affectsNames(n, molecules)).toEqual(["Chain A", "POPC"]);
  });
  it("empty affects (G4 not landed) yields no chips", () => {
    const n = { id: "n", severity: "info", code: "c", title: "t", body: "b", action: null, affects: [], raw_count: 1 } as Note;
    expect(affectsNames(n, [mol("seg_a", "Chain A")])).toEqual([]);
  });
});
