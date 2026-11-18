import { describe, expect, it } from "vitest";
import type { LaneCard } from "../../lib/api/admin";
import { laneHealth, policyError, policySummary, poolText, runCounts } from "./lanes";

function card(over: Partial<LaneCard> = {}): LaneCard {
  return {
    lane: "repository", title: "Repository", about: "", queue: "validation.repo.celery",
    deployment: "bat3-repo-worker", waiting: 0, paused: false, running: 0, reserved: 0,
    consumers: [{ name: "celery@a", active: [], reserved: 0 }],
    pool: { replicas: 2, ready: 2, updated: 2, image: "img:1", scale: [0, 300], crashing: 0 },
    runs: {}, retry_waiting: 0, retry_policy: null, token: null, errors: [], ...over,
  };
}

const POLICY = { enabled: true, max_attempts: 3, delay_minutes: 60, incomplete: true, worker_lost: true };

describe("lanes", () => {
  it("flags waiting work without workers, failing pods and pauses", () => {
    expect(laneHealth(card({ waiting: 5, consumers: [] })).tone).toBe("error");
    expect(laneHealth(card({ pool: { ...card().pool!, crashing: 1 } })).text).toBe("1 worker failing");
    expect(laneHealth(card({ paused: true })).tone).toBe("warn");
    expect(laneHealth(card({ running: 2 })).text).toBe("busy");
    expect(laneHealth(card()).tone).toBe("ok");
    expect(laneHealth(card({ consumers: [] })).text).toBe("no workers");
  });

  it("describes the pool and the policy", () => {
    expect(poolText(card().pool)).toBe("2/2 ready · img:1");
    expect(poolText(null)).toBe("no worker deployment");
    expect(policySummary({ ...POLICY, enabled: false })).toBe("Automatic retries off.");
    expect(policySummary(POLICY)).toBe("Retries incomplete runs and lost workers: up to 3 attempts, 60 min apart.");
    expect(policySummary({ ...POLICY, worker_lost: false })).toMatch(/^Retries incomplete runs:/);
  });

  it("validates policy drafts like the server", () => {
    expect(policyError(POLICY)).toBeNull();
    expect(policyError({ ...POLICY, max_attempts: 11 })).toMatch(/Attempts/);
    expect(policyError({ ...POLICY, delay_minutes: 0 })).toMatch(/Delay/);
    expect(policyError({ ...POLICY, delay_minutes: 2.5 })).toMatch(/Delay/);
  });

  it("orders run counts", () => {
    expect(runCounts({ success: 40, running: 3, retry_scheduled: 2, cancelled: 1 }))
      .toBe("3 running · 2 waiting to retry · 40 success · 1 cancelled");
  });
});
