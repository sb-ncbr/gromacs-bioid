import { describe, expect, it } from "vitest";
import type { MoleculeKind, NoteSeverity, RunStatus, StageStatus, ViewModel } from "./types";
import navmsFinished from "./fixtures/navms-finished.json";
import navmsRunning from "./fixtures/navms-running.json";
import navmsQueued from "./fixtures/navms-queued.json";
import navmsFailed from "./fixtures/navms-failed.json";
import largeFinished from "./fixtures/large-finished.json";
import largeRunning from "./fixtures/large-running.json";

/**
 * Conformance of the handoff fixtures (bioid_ui_handoff/fixtures/) to the
 * view-model contract, plus the SPEC.md §7 data-level facts the acceptance
 * checklist relies on. These fixtures drive Storybook-style states and the
 * redesigned page's component tests.
 */

const FIXTURES: Record<string, unknown> = {
  "navms-finished": navmsFinished,
  "navms-running": navmsRunning,
  "navms-queued": navmsQueued,
  "navms-failed": navmsFailed,
  "large-finished": largeFinished,
  "large-running": largeRunning,
};

const RUN_STATUSES: RunStatus[] = ["queued", "running", "finished", "failed"];
const STAGE_STATUSES: StageStatus[] = ["done", "active", "waiting", "failed"];
const KINDS: MoleculeKind[] = ["protein", "nucleic", "small_molecule", "lipid", "unknown", "ion", "water"];
const SEVERITIES: NoteSeverity[] = ["attention", "info"];

function asViewModel(raw: unknown): ViewModel {
  return raw as ViewModel;
}

describe("fixture conformance to the view-model contract", () => {
  for (const [name, raw] of Object.entries(FIXTURES)) {
    it(`${name}: enums and required molecule fields`, () => {
      const vm = asViewModel(raw);
      expect(RUN_STATUSES).toContain(vm.run.status);
      expect(vm.progress.stages).toHaveLength(6);
      for (const s of vm.progress.stages) expect(STAGE_STATUSES).toContain(s.status);
      for (const n of vm.notes) expect(SEVERITIES).toContain(n.severity);
      for (const m of vm.molecules) {
        expect(KINDS).toContain(m.kind);
        expect(typeof m.id).toBe("string");
        expect(typeof m.display_name).toBe("string");
        expect(typeof m.copies).toBe("number");
        expect(typeof m.atoms_per_copy).toBe("number");
        expect(m.descriptor).toBeTypeOf("object");
        expect(Array.isArray(m.note_ids)).toBe(true);
        expect(Array.isArray(m.residue_names)).toBe(true);
        if (m.result?.state === "exact") expect(m.result.confidence).toBeNull();
      }
    });
  }
});

describe("fixture facts the acceptance checklist relies on (SPEC.md §7)", () => {
  it("navms-finished: 10 rows, identified and exact only", () => {
    const vm = asViewModel(navmsFinished);
    expect(vm.molecules).toHaveLength(10);
    expect(vm.run.status).toBe("finished");
    expect(vm.progress.stages.every((s) => s.status === "done")).toBe(true);
    const states = vm.molecules.map((m) => m.result!.state);
    expect(new Set(states)).toEqual(new Set(["identified", "exact"]));
  });

  it("navms-running: search step active, 6 of 10 searched, no results yet", () => {
    const vm = asViewModel(navmsRunning);
    expect(vm.progress.stages.find((s) => s.key === "search")!.status).toBe("active");
    expect(vm.progress.molecules_done).toBe(6);
    expect(vm.progress.molecules_total).toBe(10);
    expect(vm.molecules.every((m) => m.result === null)).toBe(true);
  });

  it("navms-queued: queue state with an empty molecule list", () => {
    const vm = asViewModel(navmsQueued);
    expect(vm.run.status).toBe("queued");
    expect(vm.molecules).toHaveLength(0);
  });

  it("navms-failed: error banner, search step failed", () => {
    const vm = asViewModel(navmsFailed);
    expect(vm.run.status).toBe("failed");
    expect(vm.error).not.toBeNull();
    expect(vm.progress.stages.find((s) => s.key === "search")!.status).toBe("failed");
  });

  it("large-finished: 25 molecules incl. lead and not-identified, 7 notes", () => {
    const vm = asViewModel(largeFinished);
    expect(vm.molecules).toHaveLength(25);
    expect(vm.notes).toHaveLength(7);
    const states = vm.molecules.map((m) => m.result!.state);
    expect(states).toContain("lead");
    expect(states).toContain("not_identified");
  });

  it("large-running: 25 molecules, search active at 12 of 25", () => {
    const vm = asViewModel(largeRunning);
    expect(vm.molecules).toHaveLength(25);
    expect(vm.progress.molecules_done).toBe(12);
    expect(vm.progress.molecules_total).toBe(25);
  });
});
