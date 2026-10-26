import { describe, expect, it } from "vitest";
import type { Molecule, Note, Stage } from "../viewmodel";
import type { ViewModel } from "../viewmodel";
import {
  AFFECTS_VISIBLE,
  affectsNames,
  factsLine,
  hiddenNotesFooter,
  humanDuration,
  leftLine,
  notesPill,
  stepFill,
  timingsLine,
  type RunProgress,
} from "./stripModel";
import navmsFinishedRaw from "../viewmodel/fixtures/navms-finished.json";
import navmsRunningRaw from "../viewmodel/fixtures/navms-running.json";

const finished = navmsFinishedRaw as unknown as ViewModel;
const running = navmsRunningRaw as unknown as ViewModel;

const stage = (over: Partial<Stage>): Stage =>
  ({ key: "read", label: "Read files", status: "done", duration_s: null, ...over } as Stage);

const prog = (over: Partial<RunProgress>): RunProgress => ({
  stages: [],
  molecules_done: null,
  molecules_total: null,
  typical: null,
  queue_position: null,
  ...over,
});

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

describe("leftLine (SPEC.md §3.3 wording)", () => {
  it("finished: \"Finished in 1 h 35 min\" from step durations", () => {
    const stages = [stage({ duration_s: 3600 }), stage({ label: "Find molecules", duration_s: 35 * 60 })];
    expect(leftLine("finished", prog({ stages }))).toBe("Finished in 1 h 35 min");
    expect(leftLine("finished", prog({ stages: [stage({})] }))).toBe("Finished");
  });
  it("queued: queue position only when the backend knows it (G2)", () => {
    expect(leftLine("queued", prog({}))).toBe("Waiting in the queue");
    expect(leftLine("queued", prog({ queue_position: 1 }))).toBe("Waiting in the queue · 1 run ahead of yours");
    expect(leftLine("queued", prog({ queue_position: 2 }))).toBe("Waiting in the queue · 2 runs ahead of yours");
  });
  it("running: active step wording (navms-running fixture)", () => {
    expect(leftLine("running", running.progress)).toBe("Search databases… step 4 of 6");
  });
  it("failed: \"Stopped at step 4: Search databases, after 47 min\"", () => {
    const stages = [
      stage({ duration_s: 60 }),
      stage({ label: "Find molecules", duration_s: 60 }),
      stage({ label: "Describe molecules", duration_s: 60 }),
      stage({ label: "Search databases", status: "failed", duration_s: 44 * 60 }),
    ];
    expect(leftLine("failed", prog({ stages }))).toBe("Stopped at step 4: Search databases, after 47 min");
  });
});

describe("timingsLine", () => {
  it("joins non-waiting steps with durations; null when nothing ran", () => {
    const stages = [stage({ duration_s: 600 }), stage({ label: "Find molecules", duration_s: 7 }), stage({ label: "Describe molecules", status: "waiting" })];
    expect(timingsLine(stages)).toBe("Read files 10 min · Find molecules 7 s");
    expect(timingsLine([stage({})])).toBeNull();
  });
});

describe("stepFill", () => {
  it("done/failed full, waiting empty", () => {
    const p = prog({});
    expect(stepFill(stage({}), p)).toBe(1);
    expect(stepFill(stage({ status: "failed" }), p)).toBe(1);
    expect(stepFill(stage({ status: "waiting" }), p)).toBe(0);
  });
  it("active: molecules_done/total ratio, or -1 (indeterminate) without counts", () => {
    const s = stage({ status: "active" });
    expect(stepFill(s, prog({ molecules_done: 12, molecules_total: 25 }))).toBeCloseTo(0.48);
    expect(stepFill(s, prog({}))).toBe(-1);
  });
  it("navms-running active step fills by its searched molecules", () => {
    const i = running.progress.stages.findIndex((s) => s.status === "active");
    expect(running.progress.stages[i].label).toBe("Search databases");
    expect(stepFill(running.progress.stages[i], running.progress)).toBeCloseTo(
      running.progress.molecules_done! / running.progress.molecules_total!,
    );
  });
});

describe("factsLine (running)", () => {
  it("composes searched/elapsed/typical parts, omitting unknowns (G2)", () => {
    const f = factsLine("running", prog({ molecules_done: 12, molecules_total: 25, typical: "30–120 min" }), 33 * 60)!;
    expect(f.searched).toBe("12 of 25 molecules searched");
    expect(f.elapsed).toBe("33 min elapsed");
    expect(f.typical).toBe("usually 30–120 min");
    expect(f.closeNote).toBe("You can close this page; results stay at this link.");
  });
  it("falls back to summed step durations; null when not running", () => {
    const f = factsLine("running", prog({ stages: [stage({ duration_s: 120 })] }), null)!;
    expect(f.elapsed).toBe("2 min elapsed");
    expect(factsLine("finished", prog({}), null)).toBeNull();
  });
});

describe("notesPill", () => {
  const note = (severity: Note["severity"], title = "t"): Note => ({
    id: title, severity, code: "c", title, body: "b", action: null, affects: [], raw_count: 1,
  });
  it("counts per severity, leads with the most severe title", () => {
    expect(notesPill([])).toBeNull();
    const p = notesPill([note("info", "FYI"), note("attention", "Careful"), note("info", "FYI2")])!;
    expect(p.attention).toBe(1);
    expect(p.info).toBe(2);
    expect(p.total).toBe(3);
    expect(p.leadTitle).toBe("Careful");
    expect(p.others).toBe(2);
    expect(p.needsAttention).toBe(true);
  });
});

describe("affectsNames + footer (G4)", () => {
  const mol = (id: string, display_name: string): Molecule => ({ id, display_name }) as Molecule;
  it("maps ids to chips, drops unknowns, caps at 6 in the renderer", () => {
    const n = {
      id: "n", severity: "info", code: "c", title: "t", body: "b", action: null,
      affects: ["seg_a", "seg_unknown", "seg_b"], raw_count: 1,
    } as Note;
    expect(affectsNames(n, [mol("seg_a", "Chain A"), mol("seg_b", "POPC")])).toEqual([
      { id: "seg_a", name: "Chain A" },
      { id: "seg_b", name: "POPC" },
    ]);
    expect(AFFECTS_VISIBLE).toBe(6);
  });
  it("footer only when technical messages were hidden", () => {
    expect(hiddenNotesFooter(0)).toBeNull();
    expect(hiddenNotesFooter(4)).toBe("4 technical messages that don't affect results are in Technical details");
    expect(hiddenNotesFooter(finished.hidden_note_count)).not.toBeNull();
  });
});
