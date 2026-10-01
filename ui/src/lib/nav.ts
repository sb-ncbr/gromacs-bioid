/** Deep-linkable run-page state: segment + tab live in the URL query. */

export const TABS = [
  "overview",
  "input",
  "signatures",
  "identifiers",
  "verification",
  "warnings",
] as const;

export type TabKey = (typeof TABS)[number];

export const DEFAULT_TAB: TabKey = "overview";
export const DEFAULT_SEGMENT = "SYSTEM";

export interface RunQuery {
  segment: string;
  tab: TabKey;
}

const TAB_SET: ReadonlySet<string> = new Set(TABS);

export function parseRunQuery(search: string): RunQuery {
  const params = new URLSearchParams(search);
  const segment = params.get("segment")?.trim();
  const tab = params.get("tab") ?? "";
  return {
    segment: segment ? segment : DEFAULT_SEGMENT,
    tab: TAB_SET.has(tab) ? (tab as TabKey) : DEFAULT_TAB,
  };
}

export function buildRunUrl(runId: string, query?: Partial<RunQuery>): string {
  const params = new URLSearchParams();
  if (query?.segment && query.segment !== DEFAULT_SEGMENT) {
    params.set("segment", query.segment);
  }
  if (query?.tab && query.tab !== DEFAULT_TAB) {
    params.set("tab", query.tab);
  }
  const qs = params.toString();
  return `/runs/${encodeURIComponent(runId)}${qs ? `?${qs}` : ""}`;
}
