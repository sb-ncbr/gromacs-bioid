import { afterEach, describe, expect, it, vi } from "vitest";
import type { AdminOverview, AdminRun } from "../../lib/api/admin";
import { isSectionError, loadSession, saveSession } from "../../lib/api/admin";
import {
  formatBytes,
  formatDuration,
  healthSummary,
  isResolverCache,
  parseCustomDays,
  relativeTime,
  retentionSummary,
  shortDate,
  statusTone,
  toMs,
} from "./format";

const NOW = Date.parse("2026-11-10T12:00:00Z");

describe("formatBytes", () => {
  it("uses binary units with one decimal below 10", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1023)).toBe("1023 B");
    expect(formatBytes(1536)).toBe("1.5 KiB");
    expect(formatBytes(1024 * 1024)).toBe("1 MiB");
    expect(formatBytes(42 * 1024 ** 3)).toBe("42 GiB");
    expect(formatBytes(3.25 * 1024 ** 4)).toBe("3.3 TiB");
  });
  it("shows a dash for missing or invalid sizes", () => {
    expect(formatBytes(null)).toBe("—");
    expect(formatBytes(undefined)).toBe("—");
    expect(formatBytes(-1)).toBe("—");
    expect(formatBytes(Number.NaN)).toBe("—");
  });
});

describe("relativeTime / formatDuration", () => {
  it("formats past and future offsets", () => {
    expect(relativeTime(NOW - 2_000, NOW)).toBe("just now");
    expect(relativeTime(NOW - 12_000, NOW)).toBe("12s ago");
    expect(relativeTime(NOW - 5 * 60_000, NOW)).toBe("5m ago");
    expect(relativeTime(NOW - 3 * 3_600_000, NOW)).toBe("3h ago");
    expect(relativeTime(NOW - 2 * 86_400_000, NOW)).toBe("2d ago");
    expect(relativeTime(NOW + 5 * 60_000, NOW)).toBe("in 5m");
    expect(relativeTime(null, NOW)).toBe("—");
  });
  it("formats running durations", () => {
    expect(formatDuration(45)).toBe("45s");
    expect(formatDuration(720)).toBe("12m");
    expect(formatDuration(3_900)).toBe("1h 05m");
    expect(formatDuration(183_600)).toBe("2d 3h");
    expect(formatDuration(-3)).toBe("0s");
  });
  it("reads ISO strings and unix seconds", () => {
    expect(toMs("2026-11-10T12:00:00Z")).toBe(NOW);
    expect(toMs(NOW / 1000)).toBe(NOW);
    expect(toMs("nope")).toBeNull();
    expect(toMs(null)).toBeNull();
  });
});

describe("retentionSummary", () => {
  it("describes each policy", () => {
    expect(retentionSummary({ policy: "preserve", days: null, expires_at: null }, NOW)).toBe("kept indefinitely");
    const dec = new Date(2026, 11, 10, 12).toISOString();
    expect(retentionSummary({ policy: "default", days: 30, expires_at: dec }, NOW)).toBe(
      "30 days (default) · expires 10 Dec",
    );
    expect(retentionSummary({ policy: "days", days: 90, expires_at: dec }, NOW)).toBe("90 days · expires 10 Dec");
    expect(retentionSummary({ policy: "days", days: 1, expires_at: null }, NOW)).toBe("1 day after it finishes");
  });
  it("says expired once the date passed, with the year when not this one", () => {
    const past = new Date(2025, 10, 2, 12).toISOString();
    expect(retentionSummary({ policy: "days", days: 7, expires_at: past }, NOW)).toBe("7 days · expired 2 Nov 2025");
    expect(shortDate(null, NOW)).toBe("—");
  });
});

describe("small helpers", () => {
  it("tones statuses", () => {
    expect(statusTone("success")).toBe("ok");
    expect(statusTone("failed")).toBe("error");
    expect(statusTone("running")).toBe("info");
    expect(statusTone("queued")).toBe("warn");
    expect(statusTone("cancelled")).toBe("muted");
  });
  it("parses custom days strictly", () => {
    expect(parseCustomDays("30")).toBe(30);
    expect(parseCustomDays(" 365 ")).toBe(365);
    expect(parseCustomDays("0")).toBeNull();
    expect(parseCustomDays("366")).toBeNull();
    expect(parseCustomDays("2.5")).toBeNull();
    expect(parseCustomDays("")).toBeNull();
  });
  it("flags the resolver cache", () => {
    expect(isResolverCache("resolver_cache.sqlite3")).toBe(true);
    expect(isResolverCache("notes.txt")).toBe(false);
  });
  it("tells a failed section from a partial one", () => {
    expect(isSectionError({ error: "boom" })).toBe(true);
    expect(isSectionError({ queues: [], paused: [], error: "Redis not configured" })).toBe(false);
    expect(isSectionError([])).toBe(false);
  });
});

function run(over: Partial<AdminRun>): AdminRun {
  return {
    run_id: "r",
    status: "failed",
    run_name: null,
    input_kind: null,
    preset: null,
    created_at: "2026-11-10T11:00:00Z",
    started_at: null,
    finished_at: null,
    updated_at: null,
    warning_count: 0,
    error: null,
    retention: { policy: "default", days: 30, expires_at: null },
    has_owner_token: false,
    example: false,
    ...over,
  };
}

describe("healthSummary", () => {
  it("counts what the strip shows and leaves failed sections unknown", () => {
    const o: AdminOverview = {
      time: NOW / 1000,
      code_version: "v1",
      queues: { queues: [{ name: "a", waiting: 2 }, { name: "b", waiting: 3 }], paused: [] },
      workers: { error: "x" },
      deployments: [
        {
          name: "d",
          label: "D",
          replicas: 2,
          ready: 1,
          updated: 2,
          image: "i",
          scale: null,
          restartable: true,
          pods: [
            { name: "d-1", phase: "Running", ready: true, restarts: 2, waiting: null, last_exit: null, started: null, node: null, deleting: false },
            { name: "d-2", phase: "Pending", ready: false, restarts: 0, waiting: null, last_exit: null, started: null, node: null, deleting: false },
          ],
        },
        { name: "e", label: "E", error: "gone" },
      ],
      runs: {
        total: 3,
        by_status: {},
        submitted_24h: 0,
        submitted_7d: 0,
        active: [run({ status: "running" })],
        recent_failures: [run({}), run({ created_at: "2026-11-01T00:00:00Z" })],
        recent: [],
        expiring_soon: [],
      },
      storage: { error: "x" },
      retention: { error: "x" },
      limits: { submit_per_hour: 30, queue_cap: 40, max_files: 50 },
    };
    expect(healthSummary(o, NOW)).toEqual({
      waiting: 5,
      activeRuns: 1,
      failed24h: 1,
      failed24hCapped: false,
      podsNotReady: 1,
      podsRestarted: 1,
    });
    const broken = { ...o, queues: { queues: [], paused: [], error: "Redis not configured" }, runs: { error: "x" }, deployments: { error: "x" } };
    expect(healthSummary(broken, NOW)).toMatchObject({ waiting: null, activeRuns: null, failed24h: null, podsNotReady: null });
  });
});

describe("admin session storage", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("round-trips and drops expired sessions", () => {
    const mem = new Map<string, string>();
    vi.stubGlobal("sessionStorage", {
      getItem: (k: string) => mem.get(k) ?? null,
      setItem: (k: string, v: string) => void mem.set(k, v),
      removeItem: (k: string) => void mem.delete(k),
    });
    saveSession({ token: "t", expires_at: NOW / 1000 + 60 });
    expect(loadSession(NOW)).toEqual({ token: "t", expires_at: NOW / 1000 + 60 });
    expect(loadSession(NOW + 120_000)).toBeNull();
    saveSession(null);
    expect(loadSession(NOW)).toBeNull();
  });
  it("survives a storage that throws", () => {
    vi.stubGlobal("sessionStorage", {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => {
        throw new Error("denied");
      },
      removeItem: () => {},
    });
    expect(() => saveSession({ token: "t", expires_at: 1 })).not.toThrow();
    expect(loadSession(NOW)).toBeNull();
  });
});
