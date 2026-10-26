import { describe, expect, it } from "vitest";
import { steps } from "./steps";

const NOW = Date.parse("2026-10-26T12:00:00Z");
const t = (task_id: string, status: string, started_at: string | null = null, finished_at: string | null = null) => ({
  task_id,
  status,
  started_at,
  finished_at,
});

describe("steps (SPEC.md §3.3)", () => {
  it("maps every pipeline task to one of the six steps", () => {
    const out = steps(
      [
        t("discover_input", "success"),
        t("load_simulation", "success"),
        t("repair_topology", "success"),
        t("unwrap_periodic_boundaries", "success"),
        t("analyze_universe", "success"),
        t("generate_signatures", "success"),
        t("identify_molecules", "running"),
        t("verify_results", "pending"),
        t("export_results", "pending"),
        t("render_png", "pending"),
      ],
      NOW,
    );
    expect(out.map((s) => s.key)).toEqual(["read", "find", "describe", "search", "check", "save"]);
    expect(out[0].status).toBe("done");
    expect(out[2].status).toBe("done");
    expect(out[3].status).toBe("active");
    expect(out[4].status).toBe("waiting");
  });

  it("a warning still counts as done", () => {
    const out = steps([t("analyze_universe", "warning")], NOW);
    expect(out.find((s) => s.key === "find")!.status).toBe("done");
  });

  it("any failed task fails its step", () => {
    const out = steps([t("identify_molecules", "failed")], NOW);
    expect(out.find((s) => s.key === "search")!.status).toBe("failed");
  });

  it("keeps a step waiting until all of its tasks finish", () => {
    const out = steps(
      [t("discover_input", "success"), t("load_simulation", "pending"), t("repair_topology", "success"), t("unwrap_periodic_boundaries", "success")],
      NOW,
    );
    expect(out.find((s) => s.key === "read")!.status).toBe("waiting");
  });

  it("computes durations from the task envelope", () => {
    const out = steps(
      [
        t("discover_input", "success", "2026-10-26T10:00:00Z", "2026-10-26T10:00:04Z"),
        t("load_simulation", "success", "2026-10-26T10:00:02Z", "2026-10-26T10:00:30Z"),
        t("repair_topology", "success"),
        t("unwrap_periodic_boundaries", "success"),
      ],
      NOW,
    );
    expect(out.find((s) => s.key === "read")!.duration_s).toBe(30);
  });

  it("times the active step from its start to now", () => {
    const out = steps([t("identify_molecules", "running", "2026-10-26T11:58:40Z")], NOW);
    const search = out.find((s) => s.key === "search")!;
    expect(search.status).toBe("active");
    expect(search.duration_s).toBe(80);
  });

  it("tolerates missing or malformed task lists", () => {
    expect(steps(null, NOW).every((s) => s.status === "waiting")).toBe(true);
    expect(steps(undefined, NOW)).toHaveLength(6);
  });
});
