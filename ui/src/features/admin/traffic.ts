/** Pure helpers for the admin Traffic section (tested in traffic.test.ts). */
import { TRAFFIC_WINDOWS, type TrafficBucket, type TrafficWindow } from "../../lib/api/admin";
import type { Tone } from "./format";

const HOUR = 3_600_000;
const DAY = 86_400_000;
/** Never draw more buckets than this (a stray "from" years back). */
const MAX_BUCKETS = 5_000;

export interface SeriesPoint {
  /** Bucket start, ms (UTC). */
  t: number;
  requests: number;
  pageviews: number;
  visitors: number;
}

/** "2026-11-10T14" / "2026-11-10" (UTC) -> ms; null when unparseable. */
export function parseBucket(key: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}))?$/.exec(key);
  if (!m) return null;
  return Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]), m[4] ? Number(m[4]) : 0);
}

/** ISO time or "YYYY-MM-DD" (UTC) -> ms; null when missing or unparseable. */
function parseTime(value: string | null | undefined): number | null {
  if (!value) return null;
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? null : ms;
}

/**
 * The server leaves empty buckets out: rebuild every bucket from `from` to
 * `to` (also covering any bucket outside that range) with zeros in the gaps.
 */
export function fillSeries(
  series: TrafficBucket[],
  bucket: "hour" | "day",
  from: string | null,
  to: string | null,
): SeriesPoint[] {
  const step = bucket === "hour" ? HOUR : DAY;
  const floor = (ms: number) => Math.floor(ms / step) * step;
  const byT = new Map<number, TrafficBucket>();
  for (const b of series) {
    const t = parseBucket(b.t);
    if (t != null) byT.set(floor(t), b);
  }
  const keys = [...byT.keys()];
  const fromMs = parseTime(from);
  const toMs = parseTime(to);
  const starts = [...keys, ...(fromMs != null ? [floor(fromMs)] : [])];
  const ends = [...keys, ...(toMs != null ? [floor(toMs)] : [])];
  if (starts.length === 0 || ends.length === 0) return [];
  const end = Math.max(...ends);
  const start = Math.max(Math.min(...starts), end - (MAX_BUCKETS - 1) * step);
  const out: SeriesPoint[] = [];
  for (let t = start; t <= end; t += step) {
    const b = byT.get(t);
    out.push({ t, requests: b?.requests ?? 0, pageviews: b?.pageviews ?? 0, visitors: b?.visitors ?? 0 });
  }
  return out;
}

/** Clean axis ticks from 0 to at least `max`: steps of 1, 2 or 5 x 10^k (integers only). */
export function niceTicks(max: number, target = 4): number[] {
  if (!(max > 0)) return [0, 1];
  const raw = max / Math.max(1, target);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = Math.max(1, [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag);
  const top = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = 0; v <= top + step / 2; v += step) ticks.push(Math.round(v));
  return ticks;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const pad = (n: number) => String(n).padStart(2, "0");

/**
 * X-axis ticks: hourly buckets in local time (on round hours, a date at
 * midnight), daily buckets as UTC days (every day, week on Mondays, month).
 */
export function timeTicks(points: SeriesPoint[], bucket: "hour" | "day", maxTicks: number): { index: number; label: string }[] {
  const n = points.length;
  if (n === 0) return [];
  const limit = Math.max(2, maxTicks);
  if (bucket === "hour") {
    const step = [1, 2, 3, 6, 12, 24, 48].find((h) => n / h <= limit) ?? 96;
    const ticks: { index: number; label: string }[] = [];
    points.forEach((p, index) => {
      const d = new Date(p.t);
      const h = d.getHours();
      if (step < 24 ? h % step !== 0 : h !== 0) return;
      if (step >= 24 && Math.round(p.t / DAY) % (step / 24) !== 0) return;
      ticks.push({ index, label: h === 0 ? `${d.getDate()} ${MONTHS[d.getMonth()]}` : `${pad(h)}:00` });
    });
    return ticks;
  }
  const dayNo = (t: number) => Math.round(t / DAY);
  const dateLabel = (d: Date) => `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
  for (const step of [1, 2, 7, 14]) {
    // 1970-01-01 was a Thursday: (day + 3) % 7 === 0 on Mondays.
    const on = (t: number) => (step < 7 ? dayNo(t) % step === 0 : (dayNo(t) + 3) % step === 0);
    const ticks = points.flatMap((p, index) => (on(p.t) ? [{ index, label: dateLabel(new Date(p.t)) }] : []));
    if (ticks.length <= limit) return ticks;
  }
  for (const months of [1, 3, 6, 12]) {
    const ticks = points.flatMap((p, index) => {
      const d = new Date(p.t);
      if (d.getUTCDate() !== 1 || d.getUTCMonth() % months !== 0) return [];
      const label = d.getUTCMonth() === 0 ? String(d.getUTCFullYear()) : MONTHS[d.getUTCMonth()];
      return [{ index, label }];
    });
    if (ticks.length <= limit) return ticks;
  }
  return [];
}

/** Tooltip title of a bucket: "Tue 10 Nov, 14:00–15:00" (local) or "Tue 10 Nov" (UTC day). */
export function bucketLabel(t: number, bucket: "hour" | "day"): string {
  const d = new Date(t);
  if (bucket === "day") return `${WEEKDAYS[d.getUTCDay()]} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
  const next = new Date(t + HOUR);
  return `${WEEKDAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}, ${pad(d.getHours())}:00–${pad(next.getHours())}:00`;
}

/** Circle radius for a count: area proportional to the count (sqrt scale), never below `minR`. */
export function bubbleRadius(value: number, max: number, minR = 4, maxR = 22): number {
  if (!(max > 0) || !(value > 0)) return minR;
  return Math.max(minR, maxR * Math.sqrt(Math.min(value, max) / max));
}

/** "CZ" -> the Czech flag (regional indicator pair); "" for anything else. */
export function flagEmoji(code: string | null | undefined): string {
  if (!code || !/^[A-Za-z]{2}$/.test(code)) return "";
  return String.fromCodePoint(...[...code.toUpperCase()].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
}

export interface StatusGroup {
  group: "2xx" | "3xx" | "4xx" | "5xx" | "other";
  label: string;
  tone: Tone;
  count: number;
  /** Individual codes, most frequent first. */
  codes: { code: string; count: number }[];
}

const GROUPS: Omit<StatusGroup, "count" | "codes">[] = [
  { group: "2xx", label: "Success", tone: "ok" },
  { group: "3xx", label: "Redirect", tone: "info" },
  { group: "4xx", label: "Client error", tone: "warn" },
  { group: "5xx", label: "Server error", tone: "error" },
  { group: "other", label: "Other", tone: "muted" },
];

/** Status codes grouped by class; the four classes always, "other" only when present. */
export function statusGroups(status: Record<string, number>): StatusGroup[] {
  const groups = GROUPS.map((g) => ({ ...g, count: 0, codes: [] as { code: string; count: number }[] }));
  for (const [code, count] of Object.entries(status)) {
    const n = Number(code);
    const i = Number.isInteger(n) && n >= 200 && n < 600 ? Math.floor(n / 100) - 2 : 4;
    groups[i].count += count;
    groups[i].codes.push({ code, count });
  }
  for (const g of groups) g.codes.sort((a, b) => b.count - a.count || a.code.localeCompare(b.code));
  return groups.filter((g) => g.group !== "other" || g.count > 0);
}

/** 1284 -> "1,284"; 12_940 -> "12.9K"; 4_200_000 -> "4.2M". */
export function compactNumber(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  const short = (v: number, unit: string) => `${(v >= 100 ? Math.round(v) : Number(v.toFixed(1))).toString()}${unit}`;
  if (abs >= 1e9) return short(n / 1e9, "B");
  if (abs >= 1e6) return short(n / 1e6, "M");
  if (abs >= 1e4) return short(n / 1e3, "K");
  return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/** 84.2 -> "84 ms"; 1534 -> "1.5 s"; null -> "—". */
export function formatMs(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${Number((ms / 1000).toFixed(1))} s`;
}

/** Runs by client folded into web / MCP / API (API = everything else: scripts, other clients). */
export function runsBreakdown(byClient: Record<string, number>): { web: number; mcp: number; api: number } {
  let web = 0;
  let mcp = 0;
  let api = 0;
  for (const [client, n] of Object.entries(byClient)) {
    if (client === "web") web += n;
    else if (client === "mcp") mcp += n;
    else api += n;
  }
  return { web, mcp, api };
}

/** {a: 3, b: 5} -> [{name: "b", count: 5}, {name: "a", count: 3}]; zeros dropped. */
export function countsToList(counts: Record<string, number>): { name: string; count: number }[] {
  return Object.entries(counts)
    .filter(([, count]) => count > 0)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

export const WINDOW_LABELS: Record<TrafficWindow, string> = {
  "1h": "1 h",
  "24h": "24 h",
  "7d": "7 d",
  "30d": "30 d",
  "90d": "90 d",
  all: "All",
};

/** "in the last 24 hours" etc.; "all" names how long raw events are kept. */
export function windowPhrase(window: TrafficWindow, rawDays: number): string {
  switch (window) {
    case "1h":
      return "in the last hour";
    case "24h":
      return "in the last 24 hours";
    case "all":
      return `in the last ${rawDays} days (everything kept)`;
    default:
      return `in the last ${window.replace("d", "")} days`;
  }
}

const WINDOW_KEY = "bioid.admin.traffic.window";

export function isTrafficWindow(value: unknown): value is TrafficWindow {
  return typeof value === "string" && (TRAFFIC_WINDOWS as readonly string[]).includes(value);
}

export function loadWindow(): TrafficWindow {
  try {
    const raw = window.localStorage.getItem(WINDOW_KEY);
    return isTrafficWindow(raw) ? raw : "24h";
  } catch {
    return "24h";
  }
}

export function saveWindow(value: TrafficWindow): void {
  try {
    window.localStorage.setItem(WINDOW_KEY, value);
  } catch {
    // storage disabled: the choice lasts as long as the page
  }
}
