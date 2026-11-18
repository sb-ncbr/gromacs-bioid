/**
 * The admin page's first tab (2026-11-18): what needs attention, each queue
 * in one line and the services with problems. Everything links to its tab.
 */
import { cn } from "@e-infra/design-system";
import { CircleCheck } from "lucide-react";
import { isSectionError, type AdminOverview } from "../../lib/api/admin";
import { laneHealth } from "./lanes";
import { attention, type TabId } from "./overview";
import { formatSeconds, rowsFor, serviceLabel } from "./services";
import { Empty, Section, ToneBadge } from "./ui";

function TabLink({ tab, onTab, children }: { tab: TabId; onTab: (t: TabId) => void; children: React.ReactNode }) {
  return (
    <a href={`#${tab}`} onClick={(e) => { e.preventDefault(); onTab(tab); }}
       className="text-sm font-medium text-(--vm-accent) underline-offset-2 hover:underline">
      {children}
    </a>
  );
}

function Attention({ overview, nowMs, onTab }: { overview: AdminOverview; nowMs: number; onTab: (t: TabId) => void }) {
  const items = attention(overview, nowMs);
  return (
    <Section id="attention" title="Needs attention">
      {items.length === 0 ? (
        <p className="flex items-center gap-2 text-sm text-(--vm-fg)">
          <CircleCheck className="h-4 w-4 text-(--vm-high)" aria-hidden /> Nothing: queues, workers, services and checks look fine.
        </p>
      ) : (
        <ul className="divide-y divide-(--vm-line-2)">
          {items.map((it, i) => (
            <li key={i} className="flex flex-wrap items-center justify-between gap-2 py-1.5">
              <span className="flex min-w-0 items-center gap-2 text-sm">
                <ToneBadge tone={it.tone}>{it.tone === "error" ? "problem" : it.tone === "warn" ? "check" : "note"}</ToneBadge>
                <span className="min-w-0 break-words">{it.text}</span>
              </span>
              <TabLink tab={it.tab} onTab={onTab}>Open</TabLink>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function QueuesLine({ overview, onTab }: { overview: AdminOverview; onTab: (t: TabId) => void }) {
  const lanes = overview.lanes;
  return (
    <Section id="queues-summary" title="Queues" actions={<TabLink tab="queues" onTab={onTab}>Details</TabLink>}>
      {!lanes || isSectionError(lanes) ? (
        <Empty>{lanes ? lanes.error : "Not reported by this API version."}</Empty>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-xs text-text-muted">
            <tr>
              <th className="py-1 text-left font-normal">Queue</th>
              <th className="py-1 text-right font-normal">Waiting</th>
              <th className="py-1 text-right font-normal">Running</th>
              <th className="py-1 text-right font-normal">Workers</th>
              <th className="py-1 pl-3 text-left font-normal">State</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {lanes.map((c) => {
              const h = laneHealth(c);
              return (
                <tr key={c.queue} className="border-t border-(--vm-line-2)">
                  <td className="py-1">{c.title}</td>
                  <td className="py-1 text-right">{c.waiting ?? "—"}</td>
                  <td className="py-1 text-right">{c.running}</td>
                  <td className="py-1 text-right">{c.pool ? `${c.pool.ready ?? 0}/${c.pool.replicas ?? 0}` : c.consumers.length}</td>
                  <td className="py-1 pl-3"><ToneBadge tone={h.tone}>{h.text}</ToneBadge></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </Section>
  );
}

function ServicesLine({ overview, onTab }: { overview: AdminOverview; onTab: (t: TabId) => void }) {
  const s = overview.services;
  const rows = s && !isSectionError(s) ? rowsFor(s.last_30m, "all") : [];
  const shown = rows.filter((r) => r.errors > 0).slice(0, 5);
  const busiest = rows.length ? [...rows].sort((a, b) => (b.p95_s ?? 0) - (a.p95_s ?? 0))[0] : null;
  return (
    <Section id="services-summary" title="Databases & services (30 min)"
             actions={<TabLink tab="services" onTab={onTab}>Details</TabLink>}>
      {!s || isSectionError(s) ? (
        <Empty>{s ? s.error : "Not reported by this API version."}</Empty>
      ) : rows.length === 0 ? (
        <Empty>No calls in the last 30 minutes.</Empty>
      ) : (
        <div className="grid gap-1.5 text-sm">
          <p className="text-text-muted">
            {rows.reduce((n, r) => n + r.calls, 0)} calls to {rows.length} services
            {s.ncbi_running ? ` · ${s.ncbi_running} NCBI searches running` : ""}
            {busiest?.p95_s ? ` · slowest: ${serviceLabel(busiest.service).name} (95 % within ${formatSeconds(busiest.p95_s)})` : ""}
          </p>
          {shown.length === 0 ? (
            <p className="flex items-center gap-2"><CircleCheck className="h-4 w-4 text-(--vm-high)" aria-hidden /> No errors.</p>
          ) : (
            <ul className="divide-y divide-(--vm-line-2)">
              {shown.map((r) => (
                <li key={r.service} className="flex justify-between gap-2 py-1">
                  <span className="truncate font-mono text-xs">{serviceLabel(r.service).name}</span>
                  <span className={cn("text-xs tabular-nums", r.error_share && r.error_share >= 0.5 ? "text-(--vm-error)" : "text-(--vm-attention)")}>
                    {r.errors} of {r.calls} failed
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Section>
  );
}

export function OverviewTab({ overview, nowMs, onTab }: { overview: AdminOverview; nowMs: number; onTab: (t: TabId) => void }) {
  return (
    <div className="grid gap-4">
      <Attention overview={overview} nowMs={nowMs} onTab={onTab} />
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <QueuesLine overview={overview} onTab={onTab} />
        <ServicesLine overview={overview} onTab={onTab} />
      </div>
    </div>
  );
}
