import { describe, expect, it } from "vitest";
import { runNotices } from "./runNotices";

const NOW = Date.parse("2026-11-18T12:00:00Z");

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function status(extra: Record<string, any>): any {
  return { run_id: "r", pipeline: { run_id: "r", pipeline_name: "BAT3", status: "success" }, incomplete: [], attempts: [], ...extra };
}

describe("runNotices", () => {
  it("lists failed lookups of a finished run", () => {
    const n = runNotices(status({
      incomplete: [
        { code: "identifier_resolver_failed", service: "chembl_struct@sim", reason: "server_error", segments: ["LIG"], count: 3, example: "" },
        { code: "stage_time_budget", service: "time limit (verify_results)", reason: "budget", segments: [], count: 1, example: "" },
      ],
    }), NOW);
    expect(n.incomplete).toHaveLength(2);
    expect(n.incomplete[0]).toMatch(/chembl_struct@sim\): server error, 3 lookups$/);
    expect(n.incomplete[1]).toBe("time limit (verify_results): out of time, 1 lookup");
  });

  it("says nothing about gaps while running or after a cancel", () => {
    const gap = [{ code: "identifier_resolver_failed", service: "x", reason: "timeout", segments: [], count: 1, example: "" }];
    expect(runNotices(status({ pipeline: { status: "running" }, incomplete: gap }), NOW).incomplete).toEqual([]);
    expect(runNotices(status({ pipeline: { status: "cancelled" }, incomplete: gap }), NOW).incomplete).toEqual([]);
  });

  it("explains a waiting automatic retry", () => {
    const n = runNotices(status({
      pipeline: { status: "queued" },
      retry: { attempt: 1, max_attempts: 3, reason: "incomplete", at: NOW / 1000 + 1800 },
    }), NOW);
    expect(n.retry).toMatch(/^Attempt 1 of 3 could not reach every database\. The next attempt starts at /);
    const lost = runNotices(status({
      pipeline: { status: "queued" },
      retry: { attempt: 2, max_attempts: 3, reason: "worker_lost", at: NOW / 1000 - 5 },
    }), NOW);
    expect(lost.retry).toMatch(/was interrupted.*starts shortly/);
  });

  it("counts attempts and links reruns", () => {
    const n = runNotices(status({ attempts: [{ attempt: 1 }, { attempt: 2 }], rerun_of: "old", superseded_by: "new" }), NOW);
    expect(n.attempts).toBe("Finished on attempt 3.");
    expect(n.rerunOf).toBe("old");
    expect(n.supersededBy).toBe("new");
    expect(runNotices(null, NOW).retry).toBeNull();
  });
});
