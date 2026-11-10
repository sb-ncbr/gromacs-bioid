/**
 * Traffic: visitors, page views, runs and API requests over a chosen window
 * (GET /admin/traffic, src_new/api/traffic.py). Its own query, refetched with
 * the dashboard's "Live" switch but at most every 30 s (the server caches it
 * as long); a failure here never takes the rest of the page down.
 */
import { lazy, Suspense, useMemo, useState, type ReactNode } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  Button,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  ToggleGroup,
  ToggleGroupItem,
  cn,
} from "@e-infra/design-system";
import { Activity, Lock } from "lucide-react";
import { ApiError, apiErrorMessage } from "../../lib/api/client";
import { TRAFFIC_WINDOWS, adminApi, isUnauthorized, type TrafficStats, type TrafficWindow } from "../../lib/api/admin";
import type { Tone } from "./format";
import { useAdmin } from "./session";
import { LineKey, SERIES, SeriesTable, TrafficChart, type SeriesKey } from "./TrafficChart";
import {
  WINDOW_LABELS,
  compactNumber,
  countsToList,
  fillSeries,
  flagEmoji,
  formatMs,
  isTrafficWindow,
  loadWindow,
  runsBreakdown,
  saveWindow,
  statusGroups,
  windowPhrase,
} from "./traffic";
import { Empty, Section, SectionErrorNote } from "./ui";
import "./traffic.css";

const TrafficMap = lazy(() => import("./TrafficMap"));

const REFRESH_MS = 30_000;
const COUNTRIES_SHOWN = 10;

const DOT: Record<Tone, string> = {
  ok: "bg-(--vm-high)",
  warn: "bg-(--vm-medium)",
  error: "bg-(--vm-none)",
  info: "bg-(--vm-info)",
  muted: "bg-(--vm-low)",
};

const CLIENT_LABELS: Record<string, string> = {
  web: "Web app",
  mcp: "MCP",
  docs: "Documentation",
  api: "API (other clients)",
  script: "Scripts (curl, Python…)",
  bot: "Bots and crawlers",
};

const color = (key: SeriesKey) => SERIES.find((s) => s.key === key)!.color;
const n = (v: number) => v.toLocaleString("en");

function Kpi({
  label,
  value,
  hint,
  series,
  tone,
  title,
}: {
  label: string;
  value: string;
  hint?: ReactNode;
  series?: SeriesKey;
  tone?: Tone;
  title?: string;
}) {
  return (
    <div className="min-w-0 rounded-md border border-(--vm-line) bg-(--vm-surface-2) px-3 py-2" title={title}>
      <dt className="flex min-w-0 items-center gap-1.5 text-xs text-text-muted">
        {series && <LineKey color={color(series)} />}
        {tone && <span className={cn("h-2 w-2 shrink-0 rounded-full", DOT[tone])} aria-hidden />}
        <span className="truncate">{label}</span>
      </dt>
      <dd className="text-xl leading-tight font-semibold text-(--vm-fg)">{value}</dd>
      {hint && <dd className="truncate text-xs text-text-muted">{hint}</dd>}
    </div>
  );
}

function Panel({ title, hint, className, children }: { title: string; hint?: ReactNode; className?: string; children: ReactNode }) {
  return (
    <div className={cn("min-w-0 rounded-md border border-(--vm-line) p-3", className)}>
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <h3 className="text-sm font-semibold text-(--vm-fg)">{title}</h3>
        {hint && <p className="text-xs text-text-muted">{hint}</p>}
      </div>
      {children}
    </div>
  );
}

/** A ranked list with thin bars (value at the right, bar under the label). */
function BarList({
  items,
  barColor,
  mono = false,
  label = (name) => name,
  empty,
}: {
  items: { name: string; count: number }[];
  barColor: string;
  mono?: boolean;
  label?: (name: string) => string;
  empty: string;
}) {
  if (items.length === 0) return <Empty>{empty}</Empty>;
  const max = Math.max(1, ...items.map((i) => i.count));
  return (
    <ul className="space-y-1.5">
      {items.map((it) => (
        <li key={it.name} title={`${label(it.name)}: ${n(it.count)}`}>
          <div className="flex items-baseline justify-between gap-3">
            <span className={cn("min-w-0 truncate text-(--vm-fg)", mono ? "font-mono text-xs" : "text-sm")}>{label(it.name)}</span>
            <span className="shrink-0 text-sm tabular-nums text-(--vm-fg-2)">{n(it.count)}</span>
          </div>
          <div
            className="mt-0.5 h-1.5 rounded-r-[3px]"
            style={{ width: `${Math.max(1, (it.count / max) * 100).toFixed(1)}%`, background: barColor }}
            aria-hidden
          />
        </li>
      ))}
    </ul>
  );
}

function Countries({ data }: { data: TrafficStats }) {
  const [all, setAll] = useState(false);
  const rows = all ? data.countries : data.countries.slice(0, COUNTRIES_SHOWN);
  if (data.countries.length === 0) {
    return <Empty>{data.geoip.available ? "No located visitors in this window." : "Locations are not known yet."}</Empty>;
  }
  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Country</TableHead>
            <TableHead className="text-right">Visitors</TableHead>
            <TableHead className="text-right">Page views</TableHead>
            <TableHead className="text-right">Requests</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((c) => (
            <TableRow key={c.code}>
              <TableCell className="max-w-[14rem]">
                <span className="flex min-w-0 items-center gap-2">
                  <span className="w-5 shrink-0 text-base leading-none" aria-hidden>
                    {flagEmoji(c.code)}
                  </span>
                  <span className="truncate" title={`${c.name} (${c.code})`}>
                    {c.name}
                  </span>
                </span>
              </TableCell>
              <TableCell className="text-right tabular-nums">{n(c.visitors)}</TableCell>
              <TableCell className="text-right tabular-nums">{n(c.pageviews)}</TableCell>
              <TableCell className="text-right tabular-nums">{n(c.requests)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {data.countries.length > COUNTRIES_SHOWN && (
        <Button type="button" variant="ghost" size="sm" className="mt-1 text-xs" onClick={() => setAll((v) => !v)}>
          {all ? "Show fewer" : `Show all ${data.countries.length} countries`}
        </Button>
      )}
    </>
  );
}

function StatusCodes({ status }: { status: Record<string, number> }) {
  const groups = statusGroups(status);
  return (
    <ul className="space-y-2">
      {groups.map((g) => (
        <li key={g.group} className="min-w-0">
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="flex items-center gap-2 text-(--vm-fg)">
              <span className={cn("h-2 w-2 shrink-0 rounded-full", DOT[g.count ? g.tone : "muted"])} aria-hidden />
              <span className="font-mono text-xs">{g.group}</span>
              <span className="text-text-muted">{g.label}</span>
            </span>
            <span className="shrink-0 tabular-nums text-(--vm-fg-2)">{n(g.count)}</span>
          </div>
          {g.codes.length > 0 && (
            <p className="truncate pl-4 font-mono text-[11px] text-text-muted" title={g.codes.map((c) => `${c.code}: ${n(c.count)}`).join(", ")}>
              {g.codes.map((c) => `${c.code} ×${n(c.count)}`).join(" · ")}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

function LocationNote({ geoip }: { geoip: TrafficStats["geoip"] }) {
  return (
    <p className="mt-2 text-xs text-text-muted">
      {geoip.available ? geoip.attribution : "Locations appear once the GeoIP database is downloaded (automatic, monthly)."}
    </p>
  );
}

function TrafficBody({ data, shown, onToggle }: { data: TrafficStats; shown: Record<SeriesKey, boolean>; onToggle: (k: SeriesKey) => void }) {
  const points = useMemo(() => fillSeries(data.series, data.bucket, data.from, data.to), [data]);
  const t = data.totals;
  const runs = runsBreakdown(data.runs_by_client);
  const nothing = t.visitors + t.pageviews + t.requests === 0;

  if (nothing) {
    return (
      <div className="space-y-2">
        <Empty>Nothing was recorded {windowPhrase(data.window, data.raw_days)}.</Empty>
        {!data.geoip.available && <LocationNote geoip={data.geoip} />}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4 2xl:grid-cols-8" aria-label="Totals">
        <Kpi label="Visitors" value={compactNumber(t.visitors)} hint="distinct, bots excluded" series="visitors" />
        <Kpi label="Page views" value={compactNumber(t.pageviews)} hint="web app and docs" series="pageviews" />
        <Kpi
          label="Runs submitted"
          value={compactNumber(t.runs)}
          hint={`web ${n(runs.web)} · MCP ${n(runs.mcp)} · API ${n(runs.api)}`}
          title="Accepted submissions and reruns, by client"
        />
        <Kpi label="API requests" value={compactNumber(t.requests)} hint="status polling not counted" series="requests" />
        <Kpi label="Errors (5xx)" value={compactNumber(t.errors)} tone={t.errors > 0 ? "error" : "ok"} hint="server errors" />
        <Kpi
          label="Rate-limited (429)"
          value={compactNumber(t.rate_limited)}
          tone={t.rate_limited > 0 ? "warn" : "ok"}
          hint="refused by the limits"
        />
        <Kpi label="Countries" value={compactNumber(t.countries)} hint={data.geoip.available ? "of located visits" : "location unknown"} />
        <Kpi
          label="Response p50 / p95"
          value={t.p50_ms == null ? "—" : `${formatMs(t.p50_ms)} / ${formatMs(t.p95_ms)}`}
          hint="recorded API requests"
        />
      </dl>

      <Panel
        title="Over time"
        hint={data.bucket === "hour" ? "per hour, your local time" : "per day (UTC days)"}
      >
        <TrafficChart points={points} bucket={data.bucket} shown={shown} onToggle={onToggle} />
        <div className="mt-2">
          <SeriesTable points={points} bucket={data.bucket} />
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-5">
        <Panel title="Where visitors come from" hint="circle area ~ visitors" className="lg:col-span-3">
          <Suspense fallback={<Skeleton className="h-72 w-full sm:h-80 lg:h-[26rem]" />}>
            <TrafficMap places={data.places} fitKey={data.window} />
          </Suspense>
          <LocationNote geoip={data.geoip} />
        </Panel>
        <Panel title="Countries" className="lg:col-span-2">
          <Countries data={data} />
        </Panel>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Panel title="Top pages" hint="page views">
          <BarList items={data.pages} barColor={color("pageviews")} mono empty="No page views." />
        </Panel>
        <Panel title="Top API endpoints" hint="requests">
          <BarList items={data.endpoints} barColor={color("requests")} mono empty="No API requests." />
        </Panel>
        <Panel title="Referrers" hint="page views from other sites">
          <BarList items={data.referrers} barColor={color("pageviews")} empty="No referring sites." />
        </Panel>
        <Panel title="Clients" hint="page views and requests">
          <BarList
            items={countsToList(data.clients)}
            barColor="var(--vm-low)"
            label={(c) => CLIENT_LABELS[c] ?? c}
            empty="No clients."
          />
        </Panel>
        <Panel title="Browsers" hint="page views and requests">
          <BarList items={countsToList(data.browsers)} barColor="var(--vm-low)" empty="No browsers." />
        </Panel>
        <Panel title="Status codes" hint="API requests">
          <StatusCodes status={data.status} />
        </Panel>
      </div>
    </div>
  );
}

export function TrafficSection({ live }: { live: boolean }) {
  const { token, signOut } = useAdmin();
  const [win, setWin] = useState<TrafficWindow>(() => loadWindow());
  const [shown, setShown] = useState<Record<SeriesKey, boolean>>({ visitors: true, pageviews: true, requests: false });
  const traffic = useQuery({
    queryKey: ["admin", "traffic", win, token],
    queryFn: async () => {
      try {
        return await adminApi.traffic(token, win);
      } catch (err) {
        if (isUnauthorized(err)) signOut(apiErrorMessage(err, "Sign in to the admin page."));
        throw err;
      }
    },
    refetchInterval: live ? REFRESH_MS : false,
    staleTime: REFRESH_MS,
    placeholderData: keepPreviousData,
    retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 1,
  });
  const data = traffic.data;

  const choose = (value: string) => {
    if (!isTrafficWindow(value)) return;
    setWin(value);
    saveWindow(value);
  };

  const selector = (
    <ToggleGroup
      type="single"
      value={win}
      onValueChange={choose}
      aria-label="Time window"
      className="rounded-md border border-(--vm-line) bg-(--vm-surface-2) p-0.5"
    >
      {TRAFFIC_WINDOWS.map((w) => (
        <ToggleGroupItem key={w} value={w} className="min-h-7 px-2 py-1 text-xs" aria-label={`Show ${windowPhrase(w, data?.raw_days ?? 90).replace(/^in /, "")}`}>
          {WINDOW_LABELS[w]}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );

  return (
    <Section id="traffic" title="Traffic" icon={Activity} actions={selector} className="bioid-traffic">
      <div className="space-y-3">
        {traffic.isError && (
          <SectionErrorNote
            what="Traffic"
            error={`${apiErrorMessage(traffic.error, traffic.error instanceof ApiError ? "The statistics failed to load." : "Could not reach the API.")}${
              data ? " Showing earlier data." : ""
            }`}
          />
        )}
        {!data ? (
          traffic.isPending && (
            <div className="space-y-3" aria-busy="true" aria-label="Loading the traffic statistics">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {Array.from({ length: 8 }, (_, i) => (
                  <Skeleton key={i} className="h-16" />
                ))}
              </div>
              <Skeleton className="h-64 w-full" />
            </div>
          )
        ) : (
          <div className={cn("transition-opacity", traffic.isPlaceholderData && "opacity-60")} aria-busy={traffic.isPlaceholderData}>
            <TrafficBody
              data={data}
              shown={shown}
              onToggle={(k) => setShown((s) => ({ ...s, [k]: !s[k] }))}
            />
          </div>
        )}
        {data && (
          <p className="flex items-start gap-1.5 border-t border-(--vm-line-2) pt-3 text-xs text-text-muted">
            <Lock className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
            <span>
              Addresses are never stored: only a keyed hash and the approximate location (city) looked up at request time. Raw
              events are kept {data.raw_days} days. Visitors with Do Not Track are not counted.
            </span>
          </p>
        )}
      </div>
    </Section>
  );
}
