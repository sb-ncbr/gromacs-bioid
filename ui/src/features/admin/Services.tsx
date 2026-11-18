/**
 * Calls per database and web service (2026-11-18): identify lookups
 * ("db:…") and every HTTP request a worker makes ("http:…", which covers
 * verification), from GET /admin/overview `services`. Measure only.
 */
import { useState } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@e-infra/design-system";
import { Activity } from "lucide-react";
import { isSectionError, type AdminOverview, type ServicesSummary } from "../../lib/api/admin";
import { relativeTime } from "./format";
import { errorBreakdown, errorTone, formatSeconds, rowsFor, serviceLabel, type StageFilter } from "./services";
import { Empty, Section, SectionErrorNote, ToneBadge } from "./ui";

type Window = "30m" | "24h";

function Toggle<T extends string>({ value, options, onChange, label }: {
  value: T; options: [T, string][]; onChange: (v: T) => void; label: string;
}) {
  return (
    <div role="group" aria-label={label} className="flex overflow-hidden rounded-md border border-(--vm-line)">
      {options.map(([v, text]) => (
        <button
          key={v}
          type="button"
          aria-pressed={value === v}
          onClick={() => onChange(v)}
          className={
            "px-2 py-1 text-xs " +
            (value === v ? "bg-(--vm-surface-2) font-medium text-(--vm-fg)" : "text-(--vm-muted) hover:text-(--vm-fg)")
          }
        >
          {text}
        </button>
      ))}
    </div>
  );
}

function NcbiLine({ s }: { s: ServicesSummary }) {
  const crowded = s.ncbi_running >= s.ncbi_alarm_at;
  return (
    <p className="text-sm text-(--vm-fg)">
      <ToneBadge tone={crowded ? "warn" : s.ncbi_running ? "info" : "muted"} className="mr-2">
        {s.ncbi_running} NCBI nr/nt search{s.ncbi_running === 1 ? "" : "es"} running
      </ToneBadge>
      <span className="text-xs text-text-muted">
        They share the database volume (~50 MB/s); alarm at {s.ncbi_alarm_at}. No lock: each takes longer.
      </span>
    </p>
  );
}

function ServiceTable({ s, window, stage }: { s: ServicesSummary; window: Window; stage: StageFilter }) {
  const rows = rowsFor(window === "30m" ? s.last_30m : s.last_24h, stage);
  if (rows.length === 0) return <Empty>No calls in this window.</Empty>;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Service</TableHead>
          <TableHead className="text-right">Calls</TableHead>
          <TableHead className="text-right">Cached</TableHead>
          <TableHead>Errors</TableHead>
          <TableHead className="text-right">Median</TableHead>
          <TableHead className="text-right">95 %</TableHead>
          <TableHead className="text-right">Retries</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => {
          const label = serviceLabel(r.service);
          const breakdown = errorBreakdown(r.outcomes);
          return (
            <TableRow key={`${r.service}|${r.stage}`}>
              <TableCell className="max-w-[18rem]">
                <span className="block truncate font-mono text-xs text-(--vm-fg)" title={r.service}>{label.name}</span>
                <span className="text-xs text-text-muted">{label.kind}</span>
              </TableCell>
              <TableCell className="text-right text-xs tabular-nums">{r.calls}</TableCell>
              <TableCell className="text-right text-xs tabular-nums">{r.cached || "—"}</TableCell>
              <TableCell className="text-xs">
                {r.errors ? (
                  <ToneBadge tone={errorTone(r.error_share, r.calls)} title={breakdown}>
                    {r.errors} ({Math.round((r.error_share ?? 0) * 100)} %)
                  </ToneBadge>
                ) : (
                  <span className="text-text-muted">0</span>
                )}
                {breakdown && <span className="mt-0.5 block text-[11px] text-text-muted">{breakdown}</span>}
              </TableCell>
              <TableCell className="text-right text-xs tabular-nums">{formatSeconds(r.p50_s)}</TableCell>
              <TableCell className="text-right text-xs tabular-nums">{formatSeconds(r.p95_s)}</TableCell>
              <TableCell className="text-right text-xs tabular-nums">{r.retries || "—"}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

function Running({ s, nowMs }: { s: ServicesSummary; nowMs: number }) {
  const [open, setOpen] = useState(false);
  if (s.running.length === 0) return null;
  return (
    <div className="mt-3">
      <button type="button" className="text-xs text-(--vm-muted) hover:text-(--vm-fg)" aria-expanded={open}
              onClick={() => setOpen(!open)}>
        {open ? "▾" : "▸"} {s.running.length} search{s.running.length === 1 ? "" : "es"} running now
      </button>
      {open && (
        <ul className="mt-1 divide-y divide-(--vm-line-2) text-xs">
          {s.running.map((r, i) => (
            <li key={i} className="flex flex-wrap justify-between gap-2 py-1">
              <span className="font-mono">{serviceLabel(r.service).name}</span>
              <span className="text-text-muted">{r.pod} · since {relativeTime(r.started * 1000, nowMs).replace(/ ago$/, "")}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ServicesSection({ services, nowMs }: { services: AdminOverview["services"]; nowMs: number }) {
  const [window, setWindow] = useState<Window>("30m");
  const [stage, setStage] = useState<StageFilter>("all");
  return (
    <Section
      id="services"
      title="Databases and services"
      icon={Activity}
      actions={
        <>
          <Toggle label="Stage" value={stage} onChange={setStage}
                  options={[["all", "All"], ["identify", "Identify"], ["verify", "Verify"]]} />
          <Toggle label="Window" value={window} onChange={setWindow} options={[["30m", "30 min"], ["24h", "24 h"]]} />
        </>
      }
    >
      {!services ? (
        <Empty>Not reported by this API version.</Empty>
      ) : isSectionError(services) ? (
        <SectionErrorNote what="Service measurements" error={services.error} />
      ) : (
        <div className="grid gap-3">
          <NcbiLine s={services} />
          {services.failing.length > 0 && (
            <p className="text-sm">
              {services.failing.map((f) => (
                <ToneBadge key={f.service} tone="error" className="mr-2">
                  {serviceLabel(f.service).name}: {f.errors}/{f.calls} failed (30 min)
                </ToneBadge>
              ))}
            </p>
          )}
          <ServiceTable s={services} window={window} stage={stage} />
          <Running s={services} nowMs={nowMs} />
        </div>
      )}
    </Section>
  );
}
