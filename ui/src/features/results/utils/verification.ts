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
  final_confidence?: number | null;  // v3.142+: always numeric; absent/null on legacy rows, render "—" (mirrors pydantic Optional)
  belief?: number | null;           // v3.142 (R-a): resolver component (calibrated agreement structure)
  skeleton_sim?: number | null;     // v3.142: skeleton-fp Tanimoto corroboration (chemical rows)
  equivalence_class_id?: string | null;  // v3.142 (Phase 4): visual-collapse class id
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
 * Main-table subset: verified hits only, stored order preserved.
 * Presentation-side filtering (allowed: filtering != sorting); the full
 * hit list stays available in the Identifiers tab (supplementary).
 * v3.140: main table shows ONLY verified matches (user requirement);
 * zero verified rows -> "failed to identify" empty-state alert.
 */
export function verifiedOnlyHits(
  hits: VerifiedHit[] | null | undefined,
): VerifiedHit[] {
  const arr = Array.isArray(hits) ? hits : [];
  return arr.filter((h) => h.is_verified);
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
 * v3.142 Phase 4: visual-only equivalence collapse. Group hits by their
 * equivalence_class_id while preserving the stored (fidelity) order;
 * the first stored row of each class is the primary (representative),
 * remaining rows are collapsible equivalents. Rows without a class id
 * (legacy runs) never group together (unique sentinel per row), and
 * raw row lists/counts are never altered — consumers still use the
 * original arrays for badges/exports.
 */
export interface HitGroup {
  primary: VerifiedHit;
  /** all members of the class including the primary, in stored order */
  members: VerifiedHit[];
}

export function groupByClass(hits: VerifiedHit[] | null | undefined): HitGroup[] {
  const arr = Array.isArray(hits) ? hits : [];
  const seen = new Map<string, HitGroup>();
  const out: HitGroup[] = [];
  arr.forEach((h, i) => {
    const key = h.equivalence_class_id ?? `__legacy__:${i}`;
    const g = seen.get(key);
    if (g) {
      g.members.push(h);
    } else {
      const ng: HitGroup = { primary: h, members: [h] };
      seen.set(key, ng);
      out.push(ng);
    }
  });
  return out;
}

/**
 * Confidence-term breakdown for tooltips (v3.142 Phase 2).
 *
 * Shows the composed terms: belief (resolver agreement structure) /
 * match (worker-primary similarity) / annotation — plus the skeleton-fp
 * corroboration when present. Terms that are not provable (null) are
 * omitted rather than fabricated as zero. Returns "" when nothing is
 * knowable (fully legacy row).
 */
export function confidenceBreakdown(h: VerifiedHit): string {
  const parts: string[] = [];
  const push = (label: string, v: number | null | undefined) => {
    if (typeof v === "number") parts.push(`${label} ${v.toFixed(1)}`);
  };
  push("belief", h.belief);
  push("match", h.similarity_score);
  push("annotation", h.annotation_quality_score);
  push("skeleton", h.skeleton_sim);
  return parts.join(" \u00b7 ");
}

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
