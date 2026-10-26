/**
 * Raw warnings → grouped user-facing notes (DATA.md §3, COPY.md §2.2/§3).
 *
 * Until backend gap G4 lands, `details` has no segment, so `affects` stays
 * empty and the "Affects" line is hidden at render time.
 */
import type { Note } from "./types";
import { SERVICE_LABELS, STAGE_LABELS } from "./labels";
import { catalog, isHidden, type CatalogEntry } from "./warningCatalog";
import type { StageKey } from "./types";

/** Warning shape (subset of the generated WarningItem; structural). */
export interface WarningView {
  code?: string;
  message?: string;
  step_id?: string | null;
  details?: Record<string, unknown> | null;
}

/** Message prefix before the first " (" — the resolver/service name (DATA.md §3.2). */
export function service(message: string | undefined): string | null {
  if (!message) return null;
  const i = message.indexOf(" (");
  const prefix = (i === -1 ? message : message.slice(0, i)).trim();
  return prefix || null;
}

/** Service prefix → display name (COPY.md §3.1). */
export function serviceLabel(prefix: string | null): string {
  if (!prefix) return "A database";
  const rule = SERVICE_LABELS.find((r) => r.pattern.test(prefix));
  return rule ? rule.label : "A database";
}

/** step_id → user-facing step label (for "during {step}" templates). */
export function stepLabel(stepId: string | null | undefined): string {
  if (!stepId) return "the run";
  const hit = (Object.keys(STAGE_LABELS) as StageKey[]).find((k) => STAGE_LABELS[k] === stepId);
  if (hit) return STAGE_LABELS[hit];
  const found = Object.entries(STAGE_TASK_LOOKUP).find(([, tasks]) => tasks.includes(stepId));
  return found ? STAGE_LABELS[found[0] as StageKey] : "the run";
}

const STAGE_TASK_LOOKUP: Record<string, string[]> = {
  read: ["discover_input", "load_simulation", "repair_topology", "unwrap_periodic_boundaries"],
  find: ["analyze_universe"],
  describe: ["generate_signatures"],
  search: ["identify_molecules"],
  check: ["verify_results"],
  save: ["export_results"],
};

/** Fill COPY.md placeholders. */
function fill(template: string, vars: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => vars[key] ?? `{${key}}`);
}

function renderNote(
  code: string,
  entry: CatalogEntry,
  vars: Record<string, string>,
  affects: string[],
  rawCount: number,
  idSuffix: string,
): Note {
  return {
    id: `${code}:${idSuffix}`,
    severity: entry.severity === "attention" ? "attention" : "info",
    code,
    title: fill(entry.title, vars),
    body: fill(entry.body, vars),
    action: entry.action ? fill(entry.action, vars) : null,
    affects,
    raw_count: rawCount,
  };
}

function segmentOf(w: WarningView): string | null {
  const seg = w.details?.segment;
  return typeof seg === "string" && seg ? seg : null;
}

export interface NotesResult {
  notes: Note[];
  hidden: number;
}

/**
 * The notes pipeline (DATA.md §3):
 *  1. drop hidden codes (count in `hidden`);
 *  2. group the rest by (code, service);
 *  3. error-severity codes are NOT notes — they live in the run banner;
 *  4. attention notes sort before info notes.
 */
export function notes(warnings: WarningView[] | null | undefined): NotesResult {
  const list = Array.isArray(warnings) ? warnings : [];
  let hidden = 0;
  const groups = new Map<string, { code: string; svc: string | null; items: WarningView[] }>();

  for (const w of list) {
    const code = w.code ?? "unknown";
    if (isHidden(code, w.message ?? "")) {
      hidden += 1;
      continue;
    }
    const svc = service(w.message);
    const key = `${code}${svc ?? ""}`;
    const group = groups.get(key) ?? { code, svc, items: [] };
    group.items.push(w);
    groups.set(key, group);
  }

  const out: Note[] = [];
  for (const { code, svc, items } of groups.values()) {
    const entry = catalog(code);
    if (entry.severity === "hidden") {
      hidden += items.length;
      continue;
    }
    if (entry.severity === "error") continue; // run banner, not a note
    const affects = items.map(segmentOf).filter((s): s is string => s != null);
    out.push(
      renderNote(
        code,
        entry,
        {
          service: serviceLabel(svc),
          n: String(items.length),
          step: stepLabel(items[0]?.step_id),
          molecule: affects[0] ?? "one molecule",
        },
        [...new Set(affects)],
        items.length,
        svc ?? "run",
      ),
    );
  }
  out.sort((a, b) => (a.severity === b.severity ? 0 : a.severity === "attention" ? -1 : 1));
  return { notes: out, hidden };
}

/**
 * Derived attention note (DATA.md §3.4): molecules with no confident match.
 * Placed first — it is usually the most severe thing on the page.
 */
export function unidentifiedNote(names: string[], ids: string[]): Note | null {
  if (names.length === 0) return null;
  const n = names.length;
  return {
    id: "derived:not_identified",
    severity: "attention",
    code: "derived_not_identified",
    title: `${n} molecule${n === 1 ? " was" : "s were"} not identified`,
    body: `${names.join(", ")}. Check their residue names and topology, or describe them in your deposition by hand.`,
    action: null,
    affects: ids,
    raw_count: n,
  };
}
