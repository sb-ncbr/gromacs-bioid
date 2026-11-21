/**
 * 2026-11-21 (mdval audit item 7): a successful run can still be partial
 * (a stage ran out of time) or incomplete (database lookups failed); the API
 * keeps status "success" and says so in `completeness` / `partial_stages`.
 * Shared by the results header, the run list and the admin page. Pure;
 * tested in runCompleteness.test.ts.
 */
export type Completeness = "complete" | "partial" | "incomplete";

const STAGES: Record<string, string> = {
  generate_signatures: "describing the molecules",
  identify_molecules: "the database search",
  verify_results: "checking the matches",
};

export function completenessOf(value: string | null | undefined): Completeness | null {
  return value === "complete" || value === "partial" || value === "incomplete" ? value : null;
}

/** "partial" / "incomplete" for a run that needs a closer look; null otherwise. */
export function completenessSuffix(value: string | null | undefined): "partial" | "incomplete" | null {
  const c = completenessOf(value);
  return c === "partial" || c === "incomplete" ? c : null;
}

export function stageLabel(stage: string): string {
  return STAGES[stage] ?? stage;
}

/** Tooltip for the pill: what is missing, in plain words. */
export function completenessHint(value: string | null | undefined, stages: readonly string[] | null | undefined): string | null {
  const c = completenessSuffix(value);
  if (c === "partial") {
    const list = (stages ?? []).map(stageLabel);
    const what = list.length > 0 ? list.join(", ") : "a stage";
    return `Finished, but ${what} ran out of time: molecules handled after the limit may have fewer matches or none.`;
  }
  if (c === "incomplete") return "Finished, but some database lookups failed; a rerun can repeat them.";
  return null;
}
