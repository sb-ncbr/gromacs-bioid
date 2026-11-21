/**
 * The admin page's tabs and its "needs attention" list (2026-11-18): what an
 * operator must look at first, from the data the overview already holds.
 * Pure; tested in overview.test.ts.
 */
import { isSectionError, type AdminOverview, type DeploymentInfo } from "../../lib/api/admin";
import { isDeploymentError, toMs, type Tone } from "./format";
import { laneHealth } from "./lanes";

export const TABS = [
  { id: "overview", label: "Overview" },
  { id: "queues", label: "Queues & workers" },
  { id: "services", label: "Databases & services" },
  { id: "cache", label: "Shared cache" },
  { id: "runs", label: "Runs" },
  { id: "deployments", label: "Deployments" },
  { id: "checks", label: "Checks & reports" },
  { id: "storage", label: "Storage & retention" },
  { id: "traffic", label: "Traffic" },
] as const;

export type TabId = (typeof TABS)[number]["id"];

/** Tab of a URL hash ("#services"); older section anchors map to their tab. */
export function tabFromHash(hash: string): TabId {
  const id = hash.replace(/^#/, "").replace(/-title$/, "");
  const alias: Record<string, TabId> = { workers: "queues", reports: "checks", retention: "storage", limits: "storage" };
  const found = TABS.find((t) => t.id === id)?.id ?? alias[id];
  return found ?? "overview";
}

export interface AttentionItem {
  tone: Tone;
  text: string;
  tab: TabId;
}

const RANK: Record<Tone, number> = { error: 0, warn: 1, info: 2, ok: 3, muted: 4 };

export function attention(o: AdminOverview, nowMs: number): AttentionItem[] {
  const out: AttentionItem[] = [];

  if (!isSectionError(o.deployments)) {
    for (const d of o.deployments) {
      if (isDeploymentError(d)) {
        out.push({ tone: "error", text: `${d.name}: ${d.error}`, tab: "deployments" });
        continue;
      }
      const pods = (d as DeploymentInfo).pods;
      const failing = pods.filter((p) => p.waiting && !p.deleting);
      const notReady = pods.filter((p) => !p.ready && !p.deleting && !p.waiting);
      if (failing.length)
        out.push({ tone: "error", tab: "deployments",
                   text: `${d.name}: ${failing.length} pod${failing.length === 1 ? "" : "s"} ${failing[0].waiting}` });
      else if (notReady.length)
        out.push({ tone: "warn", tab: "deployments",
                   text: `${d.name}: ${notReady.length} pod${notReady.length === 1 ? "" : "s"} not ready` });
    }
  }

  if (o.lanes && !isSectionError(o.lanes)) {
    for (const card of o.lanes) {
      const h = laneHealth(card);
      if (h.tone === "error" || h.tone === "warn") out.push({ tone: h.tone, text: `${card.title} queue: ${h.text}`, tab: "queues" });
      if (card.retry_waiting) out.push({ tone: "info", text: `${card.title} queue: ${card.retry_waiting} run${card.retry_waiting === 1 ? "" : "s"} waiting to retry`, tab: "queues" });
    }
  }

  if (o.services && !isSectionError(o.services)) {
    for (const f of o.services.failing)
      out.push({ tone: "error", tab: "services", text: `${f.service.replace(/^(db|http):/, "")}: ${f.errors} of ${f.calls} calls failed (30 min)` });
    if (o.services.ncbi_running >= o.services.ncbi_alarm_at)
      out.push({ tone: "warn", tab: "services", text: `${o.services.ncbi_running} NCBI nr/nt searches running at once` });
  }

  if (o.checks && !isSectionError(o.checks)) {
    const st = o.checks.status;
    if (st === "red") out.push({ tone: "error", tab: "checks", text: "Known-answers check is red" });
    else if (st === "amber") out.push({ tone: "warn", tab: "checks", text: "Known-answers check is amber" });
  }
  if (o.reports && !isSectionError(o.reports) && o.reports.open > 0)
    out.push({ tone: "info", tab: "checks", text: `${o.reports.open} open identification report${o.reports.open === 1 ? "" : "s"}` });

  if (!isSectionError(o.runs)) {
    const failed = o.runs.recent_failures.filter((r) => {
      const t = toMs(r.finished_at) ?? toMs(r.created_at);
      return t != null && nowMs - t <= 86_400_000;
    }).length;
    if (failed) out.push({ tone: "warn", tab: "runs", text: `${failed} run${failed === 1 ? "" : "s"} failed in the last 24 h` });
  }

  // a section the server could not build is itself worth a look
  const sections: [keyof AdminOverview, TabId][] = [
    ["queues", "queues"], ["workers", "queues"], ["runs", "runs"], ["storage", "storage"], ["retention", "storage"],
  ];
  for (const [key, tab] of sections)
    if (isSectionError(o[key])) out.push({ tone: "warn", tab, text: `${String(key)} unavailable: ${(o[key] as { error: string }).error}` });

  return out.sort((a, b) => RANK[a.tone] - RANK[b.tone]);
}
