import { describe, expect, it } from "vitest";
import type { ViewModel } from "../viewmodel";
import { bugReport, formatSubmitted, headerActions, metaLine, pageName, pageTitle } from "./headerModel";
import navmsRaw from "../viewmodel/fixtures/navms-finished.json";

const navms = navmsRaw as unknown as ViewModel;
const run = (over: Partial<ViewModel["run"]>): ViewModel["run"] => ({ ...navms.run, ...over });

describe("pageName (SPEC §3.1)", () => {
  it("uses the run name; falls back to the first input file stem", () => {
    expect(pageName(navms.run)).toBe("NavMs in POPC membrane");
    // fixture files are awh_conf.gro etc.; the stem of the first file wins
    expect(pageName(run({ name: "" }))).toBe(navms.run.input.files[0].replace(/\.[^.]+$/, ""));
    expect(pageName(run({ name: "  ", input: { format: "GRO", files: ["run/md.gro"], atoms: 1 } }))).toBe("md");
  });
});

describe("pageTitle (SPEC §2)", () => {
  it("prefixes with the state unless finished", () => {
    expect(pageTitle("My run", "queued")).toBe("Queued · My run · MD BioID");
    expect(pageTitle("My run", "running")).toBe("Running · My run · MD BioID");
    expect(pageTitle("My run", "finished")).toBe("My run · MD BioID");
    expect(pageTitle("My run", "failed")).toBe("Failed · My run · MD BioID");
  });
});

describe("metaLine (SPEC §3.1)", () => {
  it("format · files joined with \" + \" · atoms · submitted UTC · short id", () => {
    const line = metaLine(run({ submitted_at: "2026-10-11T19:37:20Z" }));
    expect(line).toContain(" + ");
    expect(line).toContain("submitted 11 Oct 2026, 19:37 UTC");
    expect(line).toContain(`run ${navms.run.short_id}`);
    expect(line).toContain("atoms");
  });
  it("never prints a zoneless timestamp", () => {
    expect(formatSubmitted("2026-10-11T19:37:20Z")).toMatch(/UTC$/);
  });
});

describe("headerActions (SPEC §2 table)", () => {
  it("queued/running: Cancel run only", () => {
    expect(headerActions("queued", [])).toEqual([{ kind: "cancel", label: "Cancel run", primary: false }]);
    expect(headerActions("running", [])).toHaveLength(1);
  });
  it("finished: CSV primary + JSON + Cite + Rerun", () => {
    const acts = headerActions("finished", navms.downloads);
    expect(acts[0]).toMatchObject({ kind: "download", key: "csv", primary: true });
    expect(acts.some((a) => a.kind === "download" && a.key === "json")).toBe(true);
    expect(acts.map((a) => a.kind)).toContain("cite");
    expect(acts[acts.length - 1]).toMatchObject({ kind: "rerun", primary: false });
  });
  it("failed: Rerun primary + Report a problem", () => {
    expect(headerActions("failed", [])).toEqual([
      { kind: "rerun", label: "Rerun", primary: true },
      { kind: "report", label: "Report a problem", primary: false },
    ]);
  });
});

describe("bugReport (SPEC §3.2)", () => {
  it("includes the full run id and the raw technical detail", () => {
    const txt = bugReport(navms.run, { title: "Failed", body: "b", action: "a", technical: "Traceback ..." });
    expect(txt).toContain(navms.run.id);
    expect(txt).toContain("Traceback ...");
  });
});
