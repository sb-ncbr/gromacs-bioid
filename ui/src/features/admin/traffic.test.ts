import { afterEach, describe, expect, it, vi } from "vitest";
import {
  bubbleRadius,
  bucketLabel,
  compactNumber,
  countsToList,
  fillSeries,
  flagEmoji,
  formatMs,
  loadWindow,
  niceTicks,
  parseBucket,
  runsBreakdown,
  saveWindow,
  statusGroups,
  timeTicks,
  windowPhrase,
} from "./traffic";

const H = 3_600_000;
const D = 86_400_000;

describe("fillSeries", () => {
  it("fills missing hours with zeros between from and to", () => {
    const pts = fillSeries(
      [
        { t: "2026-11-10T09", requests: 2, pageviews: 3, visitors: 1 },
        { t: "2026-11-10T12", requests: 1, pageviews: 0, visitors: 1 },
      ],
      "hour",
      "2026-11-10T08:30:00+00:00",
      "2026-11-10T13:10:00+00:00",
    );
    expect(pts.map((p) => p.t)).toEqual([8, 9, 10, 11, 12, 13].map((h) => Date.UTC(2026, 10, 10, h)));
    expect(pts.map((p) => p.pageviews)).toEqual([0, 3, 0, 0, 0, 0]);
    expect(pts.map((p) => p.requests)).toEqual([0, 2, 0, 0, 1, 0]);
  });
  it("fills days and accepts a bare date as the start (window 'all')", () => {
    const pts = fillSeries([{ t: "2026-11-08", requests: 5, pageviews: 1, visitors: 2 }], "day", "2026-11-07", "2026-11-10T12:00:00Z");
    expect(pts).toHaveLength(4);
    expect(pts[0].t).toBe(Date.UTC(2026, 10, 7));
    expect(pts[1]).toEqual({ t: Date.UTC(2026, 10, 8), requests: 5, pageviews: 1, visitors: 2 });
    expect(pts[3].visitors).toBe(0);
  });
  it("covers buckets outside the range and copes with nothing at all", () => {
    const pts = fillSeries([{ t: "2026-11-06", requests: 1, pageviews: 0, visitors: 1 }], "day", "2026-11-07", "2026-11-08T00:00:00Z");
    expect(pts.map((p) => p.t)).toEqual([Date.UTC(2026, 10, 6), Date.UTC(2026, 10, 7), Date.UTC(2026, 10, 8)]);
    expect(fillSeries([], "day", null, null)).toEqual([]);
    expect(fillSeries([], "day", null, "2026-11-08T00:00:00Z")).toEqual([]);
  });
  it("caps absurd ranges", () => {
    expect(fillSeries([], "hour", "2000-01-01T00:00:00Z", "2026-11-10T00:00:00Z").length).toBe(5000);
  });
  it("parses bucket keys as UTC", () => {
    expect(parseBucket("2026-11-10T14")).toBe(Date.UTC(2026, 10, 10, 14));
    expect(parseBucket("2026-11-10")).toBe(Date.UTC(2026, 10, 10));
    expect(parseBucket("junk")).toBeNull();
  });
});

describe("axis helpers", () => {
  it("makes clean ticks", () => {
    expect(niceTicks(0)).toEqual([0, 1]);
    expect(niceTicks(3)).toEqual([0, 1, 2, 3]);
    expect(niceTicks(37)).toEqual([0, 10, 20, 30, 40]);
    expect(niceTicks(1234)).toEqual([0, 500, 1000, 1500]);
  });
  it("ticks daily buckets on days, Mondays or months", () => {
    const days = (n: number, start = Date.UTC(2026, 9, 12)) =>
      Array.from({ length: n }, (_, i) => ({ t: start + i * D, requests: 0, pageviews: 0, visitors: 0 }));
    expect(timeTicks(days(5), "day", 8).map((t) => t.label)).toEqual(["12 Oct", "13 Oct", "14 Oct", "15 Oct", "16 Oct"]);
    const weekly = timeTicks(days(30), "day", 6);
    expect(weekly.every((t) => new Date(days(30)[t.index].t).getUTCDay() === 1)).toBe(true);
    expect(weekly[0].label).toBe("12 Oct");
    const monthly = timeTicks(days(400, Date.UTC(2026, 0, 1)), "day", 14);
    expect(monthly.map((t) => t.label).slice(0, 3)).toEqual(["2026", "Feb", "Mar"]);
    expect(timeTicks([], "day", 5)).toEqual([]);
  });
  it("ticks hourly buckets on round hours", () => {
    const start = Date.UTC(2026, 10, 9, 12);
    const pts = Array.from({ length: 25 }, (_, i) => ({ t: start + i * H, requests: 0, pageviews: 0, visitors: 0 }));
    const ticks = timeTicks(pts, "hour", 6);
    expect(ticks.length).toBeLessThanOrEqual(6);
    expect(ticks.length).toBeGreaterThan(1);
    expect(ticks.every((t) => /^\d{2}:00$|^\d+ [A-Z][a-z]{2}$/.test(t.label))).toBe(true);
  });
  it("labels buckets", () => {
    expect(bucketLabel(Date.UTC(2026, 10, 10), "day")).toBe("Tue 10 Nov 2026");
    expect(bucketLabel(Date.UTC(2026, 10, 10, 14), "hour")).toMatch(/^\w{3} \d+ \w{3}, \d{2}:00–\d{2}:00$/);
  });
});

describe("marks and labels", () => {
  it("scales bubbles by area", () => {
    expect(bubbleRadius(100, 100)).toBe(22);
    expect(bubbleRadius(25, 100)).toBe(11);
    expect(bubbleRadius(1, 10_000)).toBe(4);
    expect(bubbleRadius(0, 0)).toBe(4);
    expect(bubbleRadius(500, 100)).toBe(22);
  });
  it("makes flag emoji from ISO codes", () => {
    expect(flagEmoji("CZ")).toBe("🇨🇿");
    expect(flagEmoji("us")).toBe("🇺🇸");
    expect(flagEmoji("internal")).toBe("");
    expect(flagEmoji("")).toBe("");
    expect(flagEmoji(null)).toBe("");
  });
  it("groups status codes", () => {
    const g = statusGroups({ "200": 40, "201": 2, "304": 1, "404": 3, "429": 5, "500": 1, "503": 2 });
    expect(g.map((x) => [x.group, x.count])).toEqual([
      ["2xx", 42],
      ["3xx", 1],
      ["4xx", 8],
      ["5xx", 3],
    ]);
    expect(g[2].codes).toEqual([
      { code: "429", count: 5 },
      { code: "404", count: 3 },
    ]);
    expect(statusGroups({}).every((x) => x.count === 0)).toBe(true);
    expect(statusGroups({ None: 2 }).at(-1)).toMatchObject({ group: "other", count: 2 });
  });
  it("formats numbers and durations", () => {
    expect(compactNumber(0)).toBe("0");
    expect(compactNumber(1284)).toBe("1,284");
    expect(compactNumber(12_940)).toBe("12.9K");
    expect(compactNumber(250_400)).toBe("250K");
    expect(compactNumber(4_200_000)).toBe("4.2M");
    expect(compactNumber(null)).toBe("—");
    expect(formatMs(84.2)).toBe("84 ms");
    expect(formatMs(1534)).toBe("1.5 s");
    expect(formatMs(2000)).toBe("2 s");
    expect(formatMs(null)).toBe("—");
  });
  it("folds runs into web / MCP / API", () => {
    expect(runsBreakdown({ web: 3, mcp: 2, api: 1, script: 4 })).toEqual({ web: 3, mcp: 2, api: 5 });
    expect(runsBreakdown({})).toEqual({ web: 0, mcp: 0, api: 0 });
  });
  it("sorts counts", () => {
    expect(countsToList({ a: 3, b: 5, c: 0, d: 3 })).toEqual([
      { name: "b", count: 5 },
      { name: "a", count: 3 },
      { name: "d", count: 3 },
    ]);
  });
  it("names windows", () => {
    expect(windowPhrase("24h", 90)).toBe("in the last 24 hours");
    expect(windowPhrase("7d", 90)).toBe("in the last 7 days");
    expect(windowPhrase("all", 90)).toBe("in the last 90 days (everything kept)");
  });
});

describe("window choice", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("remembers a valid window and defaults to 24 h", () => {
    const mem = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => mem.get(k) ?? null,
      setItem: (k: string, v: string) => void mem.set(k, v),
    });
    expect(loadWindow()).toBe("24h");
    saveWindow("30d");
    expect(loadWindow()).toBe("30d");
    mem.set("bioid.admin.traffic.window", "bogus");
    expect(loadWindow()).toBe("24h");
  });
  it("survives disabled storage", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => {
        throw new Error("denied");
      },
    });
    expect(() => saveWindow("7d")).not.toThrow();
    expect(loadWindow()).toBe("24h");
  });
});
