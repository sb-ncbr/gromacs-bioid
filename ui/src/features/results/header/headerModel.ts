/**
 * Run-header model (SPEC.md §2 actions table, §3.1 header, §3.2 banner)
 * — pure derivations. Rendering lives in RunHeader.tsx / ErrorBanner.tsx.
 */
import type { DownloadEntry, RunError, RunStatus, ViewModel } from "../viewmodel";

type Run = ViewModel["run"];

/** H1: run name, else the first input file without extension (SPEC §3.1). */
export function pageName(run: Run): string {
  const name = run.name.trim();
  if (name) return name;
  const first = run.input.files[0] ?? "";
  const base = first.split("/").pop() ?? first;
  const dot = base.lastIndexOf(".");
  const stem = dot > 0 ? base.slice(0, dot) : base;
  return stem || "Run results";
}

/** Browser tab title per run state (SPEC §2). */
export function pageTitle(name: string, status: RunStatus): string {
  const suffix = `${name} · MD BioID`;
  switch (status) {
    case "queued":
      return `Queued · ${suffix}`;
    case "running":
      return `Running · ${suffix}`;
    case "failed":
      return `Failed · ${suffix}`;
    case "finished":
      return suffix;
  }
}

/** "11 Oct 2026, 19:37 UTC" — always UTC, always zoned (SPEC §3.1). */
export function formatSubmitted(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${d.getUTCDate()} ${months[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${hh}:${mm} UTC`;
}

/**
 * Meta line (SPEC §3.1):
 * "GRO · topol.top + dppc.gro · 136,768 atoms · submitted 11 Oct 2026, 19:37 UTC · run 9d90d777 [Copy link]"
 */
export function metaLine(run: Run): string {
  const parts: string[] = [];
  if (run.input.format) parts.push(run.input.format);
  if (run.input.files.length > 0) parts.push(run.input.files.join(" + "));
  if (run.input.atoms > 0) parts.push(`${run.input.atoms.toLocaleString()} atoms`);
  if (run.submitted_at) parts.push(`submitted ${formatSubmitted(run.submitted_at)}`);
  parts.push(`run ${run.short_id}`);
  return parts.join(" · ");
}

export type HeaderAction =
  | { kind: "cancel"; label: "Cancel run"; primary: false }
  | { kind: "download"; key: DownloadEntry["key"]; label: string; primary: boolean }
  | { kind: "cite"; label: "Cite"; primary: false }
  | { kind: "rerun"; label: "Rerun"; primary: boolean }
  | { kind: "report"; label: "Report a problem"; primary: false };

/** Actions by run state (SPEC §2 table). Downloads are run-level only. */
export function headerActions(status: RunStatus, downloads: DownloadEntry[]): HeaderAction[] {
  switch (status) {
    case "queued":
    case "running":
      return [{ kind: "cancel", label: "Cancel run", primary: false }];
    case "finished":
      return [
        ...downloads.map((d) => ({ kind: "download" as const, key: d.key, label: d.label, primary: d.primary })),
        { kind: "cite", label: "Cite", primary: false },
        { kind: "rerun", label: "Rerun", primary: false },
      ];
    case "failed":
      return [
        { kind: "rerun", label: "Rerun", primary: true },
        { kind: "report", label: "Report a problem", primary: false },
      ];
  }
}

/** Cancel confirm copy (SPEC §3.1, verbatim). */
export const CANCEL_CONFIRM = {
  title: "Cancel this run?",
  body: "Results so far are discarded.",
  confirm: "Cancel run",
  dismiss: "Keep running",
} as const;

/** Bug-report payload for [Copy details for a bug report] (SPEC §3.2). */
export function bugReport(run: Run, error: RunError): string {
  return [
    `MD BioID run failed`,
    `Run: ${run.id}`,
    `Name: ${run.name}`,
    `Submitted: ${run.submitted_at}`,
    ``,
    `Error: ${error.title}`,
    error.body,
    ``,
    `Technical detail:`,
    error.technical,
  ].join("\n");
}
