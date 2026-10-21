/**
 * Verification helpers – pure, no re-sorting.
 *
 * Fidelity-first ordering is set server-side by verification/manager.py
 * (see PLAN decision log 2026-10-01). The client must NOT re-sort.
 */

export interface VerifiedHit {
  identifier: string;
  ident_type: string;
  database: string;
  resolver_score?: number | null;
  similarity_score?: number | null;
  annotation_quality_score?: number | null;
  final_confidence: number | null;  // null = deterministic plateau (v3.140), render "—"
  is_verified: boolean;
  rejection_reason?: string | null;
  supporting_evidence_count?: number;
  database_url?: string | null;
  name?: string;
}

/**
 * Return hits in their original API-provided order (no re-sort).
 * Returns a shallow copy so the caller cannot mutate the source array.
 */
export function presentHits(
  hits: VerifiedHit[] | null | undefined,
): VerifiedHit[] {
  return Array.isArray(hits) ? hits.slice() : [];
}

/**
 * Best confidence = final_confidence of the first hit (hits[0]).
 * Returns null when confidence is not informative (v3.140 plateau nulling:
 * backend emits null when the value is a deterministic family constant);
 * the caller renders "—" for null. Returns 0 only for empty lists.
 */
export function bestConfidence(
  hits: VerifiedHit[] | null | undefined,
): number | null {
  const arr = Array.isArray(hits) ? hits : [];
  if (arr.length === 0) return 0;
  return typeof arr[0].final_confidence === "number"
    ? arr[0].final_confidence
    : null;
}

export const TRUNCATE_AT = 60;

/**
 * Truncate a display name to `max` characters with an ellipsis.
 * The full string should be provided in a tooltip by the caller.
 */
export function truncateName(
  name: string | null | undefined,
  max: number = TRUNCATE_AT,
): string {
  const s = (name ?? "").trim();
  if (s.length <= max) return s;
  return s.slice(0, max - 1) + "\u2026";
}
