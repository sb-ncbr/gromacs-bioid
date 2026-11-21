/**
 * The shared cache (2026-11-21): the cache-only Redis's memory and keys, how
 * often the identify stage's lookups were answered from a cache (last 24 h,
 * per hour over 48 h), and purges. Loads its own data (GET /admin/cache).
 */
import { useLayoutEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Trash2 } from "lucide-react";
import { ApiError, apiErrorMessage } from "../../lib/api/client";
import {
  adminApi,
  isSectionError,
  isUnauthorized,
  type CacheAnswers,
  type CacheKind,
  type CacheKeys,
  type CachePurge,
  type CacheRedis,
  type CacheUsage,
} from "../../lib/api/admin";
import { formatBytes, formatDuration, relativeTime } from "./format";
import { useAdmin, useAdminAction } from "./session";
import { bucketLabel, compactNumber, niceTicks, timeTicks, type SeriesPoint } from "./traffic";
import { LineKey } from "./TrafficChart";
import { ConfirmButton, Empty, Section, SectionErrorNote, Stat, ToneBadge } from "./ui";

const REFRESH_MS = 30_000;
const PURGING_MS = 2_000;
const KEY = "cache";

function pct(share: number | null | undefined): string {
  return share == null ? "–" : `${Math.round(share * 1000) / 10}%`;
}

function useCache(live: boolean) {
  const { token, signOut } = useAdmin();
  return useQuery({
    queryKey: ["admin", KEY, token],
    queryFn: async () => {
      try {
        return await adminApi.cache(token);
      } catch (err) {
        if (isUnauthorized(err)) signOut(apiErrorMessage(err, "Sign in to the admin page."));
        throw err;
      }
    },
    refetchInterval: (q) => {
      const d = q.state.data;
      if (d && !isSectionError(d) && d.purge.running) return PURGING_MS;
      return live ? REFRESH_MS : false;
    },
    retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 1,
  });
}

function usePurge() {
  const qc = useQueryClient();
  const action = useAdminAction(
    (t, v: { kind: CacheKind; cacheName?: string }) => adminApi.purgeCache(t, v.kind, v.cacheName),
    { success: (_r, v) => `Purge started: ${v.cacheName ?? (v.kind === "results" ? "all resolver results" : "all annotation scores")}`,
      failure: "Could not start the purge" },
  );
  return {
    ...action,
    mutate: (v: { kind: CacheKind; cacheName?: string }) =>
      action.mutate(v, { onSettled: () => qc.invalidateQueries({ queryKey: ["admin", KEY] }) }),
  };
}

export function CacheSection({ live, nowMs }: { live: boolean; nowMs: number }) {
  const q = useCache(live);
  const purge = usePurge();
  const d = q.data;
  if (q.isPending) return <Section id="cache" title="Shared cache" icon={Database}><Empty>Loading…</Empty></Section>;
  if (q.isError) return <Section id="cache" title="Shared cache" icon={Database}><SectionErrorNote what="The shared cache" error={apiErrorMessage(q.error, "request failed")} /></Section>;
  if (!d || isSectionError(d)) {
    return <Section id="cache" title="Shared cache" icon={Database}><SectionErrorNote what="The shared cache" error={d?.error ?? "no data"} /></Section>;
  }
  const busy = !!d.purge.running || purge.isPending;
  return (
    <div className="grid gap-4">
      <Section id="cache" title="Shared cache" icon={Database}>
        {isSectionError(d.redis) ? <SectionErrorNote what="Redis" error={d.redis.error} /> : <RedisStats redis={d.redis} usage={d.usage} />}
        <PurgeLine purge={d.purge} nowMs={nowMs} />
      </Section>
      <Section id="cache-answers" title="Lookups answered from a cache (48 h)">
        {isSectionError(d.usage) ? <SectionErrorNote what="Cache answers" error={d.usage.error} /> : <AnswersChart usage={d.usage} />}
      </Section>
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Section id="cache-kinds" title="What the cache holds">
          {isSectionError(d.keys) ? (
            <SectionErrorNote what="Key counts" error={d.keys.error} />
          ) : (
            <KindsTable keys={d.keys} nowMs={nowMs} busy={busy} onPurge={(kind) => purge.mutate({ kind })} />
          )}
        </Section>
        <Section id="cache-databases" title="Answers per database (24 h)">
          {isSectionError(d.usage) ? <SectionErrorNote what="Cache answers" error={d.usage.error} /> : <PerService usage={d.usage} />}
        </Section>
      </div>
      <Section id="cache-results" title="Resolver results per database">
        {isSectionError(d.keys) ? (
          <SectionErrorNote what="Key counts" error={d.keys.error} />
        ) : (
          <DatabasesTable keys={d.keys} busy={busy} onPurge={(cacheName) => purge.mutate({ kind: "results", cacheName })} />
        )}
      </Section>
    </div>
  );
}

function RedisStats({ redis, usage }: { redis: CacheRedis; usage: CacheUsage | { error: string } }) {
  const full = redis.max_bytes > 0 ? redis.used_bytes / redis.max_bytes : 0;
  const total = isSectionError(usage) ? null : usage.total_24h;
  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat
          label="Memory"
          value={`${formatBytes(redis.used_bytes)} / ${redis.max_bytes ? formatBytes(redis.max_bytes) : "no limit"}`}
          hint={redis.max_bytes ? `${Math.round(full * 100)}% full · ${redis.policy}` : redis.policy}
        />
        <Stat label="Keys" value={redis.keys.toLocaleString("en")} hint={`${redis.expired.toLocaleString("en")} expired`} />
        <Stat
          label="Lookups from a cache (24 h)"
          value={pct(total?.answered_share)}
          hint={total ? `${compactNumber(total.shared)} shared · ${compactNumber(total.local)} worker · ${compactNumber(total.live)} live` : undefined}
        />
        <Stat
          label="Redis hits"
          value={pct(redis.hit_share)}
          hint={`${compactNumber(redis.hits)} hits, ${compactNumber(redis.misses)} misses since start (${formatDuration(redis.uptime_s)})`}
        />
      </dl>
      <div className="h-2 overflow-hidden rounded-full bg-(--vm-surface-2)" role="img" aria-label={`Memory ${Math.round(full * 100)}% full`}>
        <div className={full >= 0.95 ? "h-full bg-(--vm-error)" : full >= 0.8 ? "h-full bg-(--vm-attention)" : "h-full bg-(--vm-accent)"} style={{ width: `${Math.min(100, full * 100)}%` }} />
      </div>
      {redis.evicted > 0 && (
        <p className="text-sm text-text-muted">
          <ToneBadge tone={full >= 0.95 ? "warn" : "muted"} className="mr-2">{redis.evicted.toLocaleString("en")} evicted</ToneBadge>
          The memory filled up: Redis drops the least recently used resolver results and measurements to make room
          (annotation scores have no expiry and are never evicted).
        </p>
      )}
    </div>
  );
}

function PurgeLine({ purge, nowMs }: { purge: CachePurge; nowMs: number }) {
  if (!purge.started_at) return null;
  const what = purge.cache_name ?? (purge.kind === "results" ? "all resolver results" : "all annotation scores");
  return (
    <p className="mt-3 text-sm text-text-muted" role="status">
      {purge.running ? (
        <>Purging {what}: {(purge.deleted ?? 0).toLocaleString("en")} keys deleted so far…</>
      ) : purge.error ? (
        <span className="text-(--vm-error)">Purge of {what} failed after {(purge.deleted ?? 0).toLocaleString("en")} keys: {purge.error}</span>
      ) : (
        <>Purged {what}: {(purge.deleted ?? 0).toLocaleString("en")} keys, {relativeTime((purge.finished_at ?? 0) * 1000, nowMs)}.</>
      )}
    </p>
  );
}

const PURGE_TEXT: Record<string, string> = {
  results:
    "Every cached resolver result goes: the next runs search each database live again until the cache refills. Runs in progress are not affected.",
  annotations: "Every cached annotation score goes: verification fetches them again.",
};

function KindsTable({ keys, nowMs, busy, onPurge }: { keys: CacheKeys; nowMs: number; busy: boolean; onPurge: (kind: CacheKind) => void }) {
  return (
    <div className="space-y-2">
      <table className="w-full text-sm">
        <thead className="text-xs text-text-muted">
          <tr>
            <th className="py-1 text-left font-medium">Kind</th>
            <th className="py-1 text-right font-medium">Keys</th>
            <th className="py-1 text-right font-medium">Memory (est.)</th>
            <th className="py-1 text-right font-medium">Expires</th>
            <th className="py-1" />
          </tr>
        </thead>
        <tbody className="divide-y divide-(--vm-line-2)">
          {keys.kinds.map((k) => (
            <tr key={k.kind}>
              <td className="py-1.5">{k.label}</td>
              <td className="py-1.5 text-right tabular-nums">{k.keys.toLocaleString("en")}</td>
              <td className="py-1.5 text-right tabular-nums">{formatBytes(k.est_bytes)}</td>
              <td className="py-1.5 text-right text-text-muted">{k.expires}</td>
              <td className="py-1.5 text-right">
                {k.purgeable && (
                  <ConfirmButton
                    label="Purge"
                    icon={Trash2}
                    ariaLabel={`Purge ${k.label.toLowerCase()}`}
                    title={`Purge ${k.label.toLowerCase()}?`}
                    description={<p>{PURGE_TEXT[k.kind]} {k.keys.toLocaleString("en")} keys.</p>}
                    confirmLabel="Purge"
                    destructive
                    disabled={busy || k.keys === 0}
                    onConfirm={() => onPurge(k.kind)}
                  />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-text-muted">
        Counted {relativeTime(keys.counted_at * 1000, nowMs)} (every 5 min); memory estimated from a sample of keys.
        {keys.other_keys > 0 && ` ${keys.other_keys.toLocaleString("en")} other keys.`}
      </p>
    </div>
  );
}

function PerService({ usage }: { usage: CacheUsage }) {
  if (usage.last_24h.length === 0) return <Empty>No database lookups in the last 24 h.</Empty>;
  return (
    <div className="max-h-96 overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-background text-xs text-text-muted">
          <tr>
            <th className="py-1 text-left font-medium">Database</th>
            <th className="py-1 text-right font-medium" title="Answered by the shared cache">Shared</th>
            <th className="py-1 text-right font-medium" title="Answered by the worker's own cache">Worker</th>
            <th className="py-1 text-right font-medium" title="Searched live">Live</th>
            <th className="py-1 text-right font-medium">From a cache</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-(--vm-line-2)">
          {usage.last_24h.map((r) => (
            <tr key={r.service}>
              <td className="py-1.5 font-mono text-xs">{r.service}</td>
              <td className="py-1.5 text-right tabular-nums">{r.shared.toLocaleString("en")}</td>
              <td className="py-1.5 text-right tabular-nums">{r.local.toLocaleString("en")}</td>
              <td className="py-1.5 text-right tabular-nums">{r.live.toLocaleString("en")}</td>
              <td className="py-1.5 text-right tabular-nums">{pct(r.answered_share)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DatabasesTable({ keys, busy, onPurge }: { keys: CacheKeys; busy: boolean; onPurge: (cacheName: string) => void }) {
  if (keys.databases.length === 0) return <Empty>No resolver results cached.</Empty>;
  const releases = new Map<string, number>();
  for (const d of keys.databases) if (d.release) releases.set(d.resolver, (releases.get(d.resolver) ?? 0) + 1);
  return (
    <div className="max-h-[32rem] overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-background text-xs text-text-muted">
          <tr>
            <th className="py-1 text-left font-medium">Database</th>
            <th className="py-1 text-left font-medium">Release</th>
            <th className="py-1 text-right font-medium">Exact</th>
            <th className="py-1 text-right font-medium">Similar</th>
            <th className="py-1" />
          </tr>
        </thead>
        <tbody className="divide-y divide-(--vm-line-2)">
          {keys.databases.map((d) => (
            <tr key={d.cache_name}>
              <td className="py-1.5 font-mono text-xs">{d.resolver}</td>
              <td className="py-1.5 text-xs">
                {d.release ?? <span className="text-text-muted">–</span>}
                {d.release && (releases.get(d.resolver) ?? 0) > 1 && <ToneBadge tone="muted" className="ml-2">several releases</ToneBadge>}
              </td>
              <td className="py-1.5 text-right tabular-nums">{d.identity.toLocaleString("en")}</td>
              <td className="py-1.5 text-right tabular-nums">{d.similarity.toLocaleString("en")}</td>
              <td className="py-1.5 text-right">
                <ConfirmButton
                  label="Purge"
                  icon={Trash2}
                  ariaLabel={`Purge cached results of ${d.cache_name}`}
                  title={`Purge ${d.cache_name}?`}
                  description={<p>{d.keys.toLocaleString("en")} cached results of this database go; its next lookups search it live.</p>}
                  confirmLabel="Purge"
                  destructive
                  disabled={busy}
                  onConfirm={() => onPurge(d.cache_name)}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// -- chart ---------------------------------------------------------------------------

type AnswerKey = "shared" | "local" | "live";

const ANSWER_SERIES: { key: AnswerKey; label: string; color: string }[] = [
  { key: "shared", label: "Shared cache", color: "var(--viz-requests)" },
  { key: "local", label: "Worker cache", color: "var(--viz-visitors)" },
  { key: "live", label: "Searched live", color: "var(--viz-pageviews)" },
];

const PLOT_H = 170;
const TOP = 10;
const AXIS_BAND = 24;
const RIGHT = 12;

function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => setWidth(Math.floor(entries[0].contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

function AnswersChart({ usage }: { usage: CacheUsage }) {
  const [ref, width] = useWidth();
  const [hover, setHover] = useState<number | null>(null);
  const points = usage.hourly.map((h) => ({ ...h, t: h.t * 1000 }));
  const n = points.length;
  const max = Math.max(0, ...points.flatMap((p) => ANSWER_SERIES.map((s) => p[s.key])));
  const yTicks = niceTicks(max, 4);
  const yTop = yTicks[yTicks.length - 1] || 1;
  const left = 10 + Math.max(...yTicks.map((t) => compactNumber(t).length)) * 7;
  const plotW = Math.max(1, width - left - RIGHT);
  const x = (i: number) => left + (n <= 1 ? plotW / 2 : (i * plotW) / (n - 1));
  const y = (v: number) => TOP + PLOT_H - (v / yTop) * PLOT_H;
  const xTicks = timeTicks(points as unknown as SeriesPoint[], "hour", Math.floor(plotW / 78));
  const active = hover != null && hover < n ? hover : null;
  const indexAt = (clientX: number, el: Element) => {
    const px = clientX - el.getBoundingClientRect().left;
    return Math.min(n - 1, Math.max(0, n <= 1 ? 0 : Math.round(((px - left) / plotW) * (n - 1))));
  };
  const onPointer = (e: PointerEvent<SVGSVGElement>) => n > 0 && setHover(indexAt(e.clientX, e.currentTarget));
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (n === 0) return;
    const cur = active ?? n - 1;
    const next = e.key === "ArrowLeft" ? cur - 1 : e.key === "ArrowRight" ? cur + 1 : e.key === "Home" ? 0 : e.key === "End" ? n - 1 : null;
    if (e.key === "Escape") setHover(null);
    if (next == null) return;
    e.preventDefault();
    setHover(Math.min(n - 1, Math.max(0, next)));
  };
  const path = (key: AnswerKey) => points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join("");
  const tipLeft = active != null && x(active) > width * 0.6;
  if (max === 0) return <Empty>No database lookups in the last 48 h.</Empty>;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
        {ANSWER_SERIES.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5">
            <LineKey color={s.color} />
            {s.label}
          </span>
        ))}
      </div>
      <div
        ref={ref}
        className="relative rounded-md outline-none focus-visible:ring-2 focus-visible:ring-(--border-focus)"
        tabIndex={0}
        aria-label="Database lookups per hour by where they were answered. Arrow keys read the values; the table below lists them."
        onKeyDown={onKey}
        onFocus={() => n > 0 && setHover((h) => h ?? n - 1)}
        onBlur={() => setHover(null)}
      >
        {width > 0 && (
          <svg
            width={width}
            height={TOP + PLOT_H + AXIS_BAND}
            className="block touch-pan-y select-none"
            onPointerMove={onPointer}
            onPointerDown={onPointer}
            onPointerLeave={() => setHover(null)}
            aria-hidden
          >
            {yTicks.map((t) => (
              <g key={t}>
                <line x1={left} x2={width - RIGHT} y1={y(t)} y2={y(t)} stroke={t === 0 ? "var(--vm-muted)" : "var(--viz-grid)"}
                  strokeOpacity={t === 0 ? 0.6 : 1} strokeWidth={1} shapeRendering="crispEdges" />
                <text x={left - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize="11" fill="var(--viz-axis)" className="tabular-nums">
                  {compactNumber(t)}
                </text>
              </g>
            ))}
            {xTicks.map((t) => (
              <text key={t.index} x={x(t.index)} y={TOP + PLOT_H + 16}
                textAnchor={x(t.index) < left + 20 ? "start" : x(t.index) > width - RIGHT - 20 ? "end" : "middle"}
                fontSize="11" fill="var(--viz-axis)" className="tabular-nums">
                {t.label}
              </text>
            ))}
            {active != null && (
              <line x1={x(active)} x2={x(active)} y1={TOP} y2={TOP + PLOT_H} stroke="var(--vm-muted)" strokeOpacity={0.7}
                strokeWidth={1} shapeRendering="crispEdges" />
            )}
            {n > 1 && ANSWER_SERIES.map((s) => (
              <path key={s.key} d={path(s.key)} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            ))}
            {active != null && ANSWER_SERIES.map((s) => (
              <circle key={s.key} cx={x(active)} cy={y(points[active][s.key])} r={4} fill={s.color} stroke="var(--viz-surface)" strokeWidth={2} />
            ))}
          </svg>
        )}
        {active != null && (
          <div
            className="pointer-events-none absolute z-10 min-w-40 rounded-md border border-(--vm-line) bg-background px-2.5 py-2 text-xs shadow-md"
            style={{ top: TOP, left: tipLeft ? undefined : x(active) + 12, right: tipLeft ? width - x(active) + 12 : undefined }}
          >
            <p className="mb-1 whitespace-nowrap text-text-muted">{bucketLabel(points[active].t, "hour")}</p>
            <ul className="space-y-0.5">
              {ANSWER_SERIES.map((s) => (
                <li key={s.key} className="flex items-center gap-2 whitespace-nowrap">
                  <LineKey color={s.color} />
                  <span className="font-semibold tabular-nums text-(--vm-fg)">{points[active][s.key].toLocaleString("en")}</span>
                  <span className="text-text-muted">{s.label.toLowerCase()}</span>
                </li>
              ))}
            </ul>
            <p className="mt-1 text-text-muted">{pct(points[active].answered_share)} from a cache</p>
          </div>
        )}
      </div>
      <HourlyTable hourly={usage.hourly} />
    </div>
  );
}

function HourlyTable({ hourly }: { hourly: (CacheAnswers & { t: number })[] }) {
  const rows = hourly.filter((h) => h.shared || h.local || h.live).reverse();
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-xs text-text-muted hover:text-(--vm-fg)">Show the numbers ({rows.length} hours with lookups)</summary>
      <div className="mt-2 max-h-64 overflow-auto rounded-md border border-(--vm-line)">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-(--vm-surface-2) text-text-muted">
            <tr>
              <th className="px-2 py-1 text-left font-medium">Hour</th>
              {ANSWER_SERIES.map((s) => <th key={s.key} className="px-2 py-1 text-right font-medium">{s.label}</th>)}
              <th className="px-2 py-1 text-right font-medium">From a cache</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-(--vm-line-2)">
            {rows.map((h) => (
              <tr key={h.t}>
                <td className="px-2 py-1 whitespace-nowrap">{bucketLabel(h.t * 1000, "hour")}</td>
                {ANSWER_SERIES.map((s) => <td key={s.key} className="px-2 py-1 text-right tabular-nums">{h[s.key].toLocaleString("en")}</td>)}
                <td className="px-2 py-1 text-right tabular-nums">{pct(h.answered_share)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
