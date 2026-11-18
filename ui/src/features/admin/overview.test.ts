import { describe, expect, it } from "vitest";
import type { AdminOverview } from "../../lib/api/admin";
import { attention, tabFromHash } from "./overview";

const NOW = Date.parse("2026-11-18T12:00:00Z");

function pod(over: Record<string, unknown> = {}) {
  return { name: "p", phase: "Running", ready: true, restarts: 0, waiting: null, last_exit: null,
           started: null, node: null, deleting: false, ...over };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function overview(over: Record<string, any> = {}): AdminOverview {
  return {
    time: NOW / 1000, code_version: "git-x",
    queues: { queues: [], paused: [] }, workers: { workers: [] },
    deployments: [{ name: "bat3-ui-worker", label: "UI", replicas: 2, ready: 2, updated: 2, image: "i",
                    scale: [0, 20], restartable: true, pods: [pod(), pod()] }],
    runs: { total: 0, by_status: {}, submitted_24h: 0, submitted_7d: 0, active: [], recent_failures: [],
            recent: [], expiring_soon: [] },
    storage: {}, retention: {}, limits: {},
    ...over,
  } as unknown as AdminOverview;
}

describe("admin overview", () => {
  it("maps hashes to tabs, old anchors included", () => {
    expect(tabFromHash("#services")).toBe("services");
    expect(tabFromHash("#deployments-title")).toBe("deployments");
    expect(tabFromHash("#workers")).toBe("queues");
    expect(tabFromHash("")).toBe("overview");
    expect(tabFromHash("#nonsense")).toBe("overview");
  });

  it("is empty when all is well", () => {
    expect(attention(overview(), NOW)).toEqual([]);
  });

  it("lists problems, most severe first, with their tab", () => {
    const items = attention(overview({
      deployments: [{ name: "bat3-ui-worker", label: "UI", replicas: 2, ready: 1, updated: 2, image: "i",
                      scale: [0, 20], restartable: true, pods: [pod(), pod({ ready: false, waiting: "CrashLoopBackOff" })] }],
      services: { last_30m: [], last_24h: [], running: [], ncbi_running: 4, ncbi_alarm_at: 3,
                  failing: [{ service: "db:chembl_struct@sim", calls: 12, errors: 8, outcomes: {} }] },
      checks: { cases: 5, status: "amber" },
      reports: { open: 2, total: 3 },
      runs: { total: 1, by_status: {}, submitted_24h: 1, submitted_7d: 1, active: [], recent: [], expiring_soon: [],
              recent_failures: [{ run_id: "r", status: "failed", finished_at: "2026-11-18T10:00:00Z", created_at: "" }] },
    }), NOW);
    expect(items.map((i) => [i.tone, i.tab])).toEqual([
      ["error", "deployments"], ["error", "services"],
      ["warn", "services"], ["warn", "checks"], ["warn", "runs"],
      ["info", "checks"],
    ]);
    expect(items[0].text).toBe("bat3-ui-worker: 1 pod CrashLoopBackOff");
    expect(items[1].text).toBe("chembl_struct@sim: 8 of 12 calls failed (30 min)");
  });

  it("flags queues with waiting work and no workers", () => {
    const items = attention(overview({
      lanes: [{ lane: "repository", title: "Repository", about: "", queue: "q", deployment: null, waiting: 4,
                paused: false, running: 0, reserved: 0, consumers: [], pool: null, runs: {}, retry_waiting: 1,
                retry_policy: null, token: null, errors: [] }],
    }), NOW);
    expect(items.map((i) => i.text)).toEqual([
      "Repository queue: waiting runs, no workers", "Repository queue: 1 run waiting to retry"]);
  });
});
