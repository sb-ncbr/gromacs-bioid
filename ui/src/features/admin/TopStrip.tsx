import { Card, cn } from "@e-infra/design-system";
import { isSectionError, type AdminOverview } from "../../lib/api/admin";
import { healthSummary, type Tone } from "./format";

const DOT: Record<Tone, string> = {
  ok: "bg-(--vm-high)",
  warn: "bg-(--vm-medium)",
  error: "bg-(--vm-none)",
  info: "bg-(--vm-info)",
  muted: "bg-(--vm-low)",
};

function Item({ href, label, value, tone, title }: { href: string; label: string; value: string; tone: Tone; title?: string }) {
  return (
    <li>
      <a
        href={href}
        title={title}
        className="flex min-w-0 items-center gap-2 rounded-md border border-(--vm-line) bg-(--vm-surface-2) px-3 py-2 text-(--vm-fg) no-underline transition-colors hover:border-(--vm-accent)"
      >
        <span className={cn("h-2 w-2 shrink-0 rounded-full", DOT[tone])} aria-hidden />
        <span className="min-w-0">
          <span className="block text-lg leading-tight font-semibold tabular-nums">{value}</span>
          <span className="block truncate text-xs text-text-muted">{label}</span>
        </span>
      </a>
    </li>
  );
}

export function TopStrip({ overview, nowMs }: { overview: AdminOverview; nowMs: number }) {
  const h = healthSummary(overview, nowMs);
  const cap = isSectionError(overview.limits) ? null : overview.limits.queue_cap;
  const unknown = "section unavailable";
  return (
    <Card className="gap-0 px-4 py-3">
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6" aria-label="Health">
        <Item
          href="#queues"
          label="Waiting in queues"
          value={h.waiting == null ? "?" : String(h.waiting)}
          tone={h.waiting == null ? "muted" : cap && h.waiting >= cap ? "error" : h.waiting > 0 ? "warn" : "ok"}
          title={h.waiting == null ? unknown : cap ? `New runs are refused at ${cap} waiting` : undefined}
        />
        <Item
          href="#runs"
          label="Active runs"
          value={h.activeRuns == null ? "?" : String(h.activeRuns)}
          tone={h.activeRuns == null ? "muted" : h.activeRuns > 0 ? "info" : "ok"}
          title={h.activeRuns == null ? unknown : undefined}
        />
        <Item
          href="#runs"
          label="Failed in 24 h"
          value={h.failed24h == null ? "?" : `${h.failed24h}${h.failed24hCapped ? "+" : ""}`}
          tone={h.failed24h == null ? "muted" : h.failed24h > 0 ? "error" : "ok"}
          title={h.failed24h == null ? unknown : "Among the 15 most recent failures"}
        />
        <Item
          href="#deployments-title"
          label="Pods not ready"
          value={h.podsNotReady == null ? "?" : String(h.podsNotReady)}
          tone={h.podsNotReady == null ? "muted" : h.podsNotReady > 0 ? "error" : "ok"}
          title={h.podsNotReady == null ? unknown : undefined}
        />
        <Item
          href="#deployments-title"
          label="Pods restarted"
          value={h.podsRestarted == null ? "?" : String(h.podsRestarted)}
          tone={h.podsRestarted == null ? "muted" : h.podsRestarted > 0 ? "warn" : "ok"}
          title={h.podsRestarted == null ? unknown : "Pods with at least one container restart"}
        />
        <li className="flex min-w-0 flex-col justify-center rounded-md border border-(--vm-line) px-3 py-2">
          <span className="block truncate font-mono text-sm font-semibold text-(--vm-fg)" title={overview.code_version || undefined}>
            {overview.code_version || "unknown"}
          </span>
          <span className="block text-xs text-text-muted">Code version</span>
        </li>
      </ul>
    </Card>
  );
}
