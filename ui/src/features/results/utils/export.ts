/**
 * Export helpers – build TSV / JSON blobs from verification hits.
 * Pure functions; no DOM side-effects until `downloadBlob` is called.
 */

import type { VerifiedHit } from "./verification";

const TSV_COLUMNS: { key: keyof VerifiedHit; header: string }[] = [
  { key: "identifier", header: "identifier" },
  { key: "ident_type", header: "ident_type" },
  { key: "database", header: "database" },
  { key: "resolver_score", header: "resolver_score" },
  { key: "similarity_score", header: "similarity_score" },
  { key: "annotation_quality_score", header: "annotation_quality_score" },
  { key: "final_confidence", header: "final_confidence" },
  { key: "is_verified", header: "is_verified" },
  { key: "rejection_reason", header: "rejection_reason" },
  { key: "supporting_evidence_count", header: "supporting_evidence_count" },
  { key: "database_url", header: "database_url" },
];

function tsvEscape(v: unknown): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  if (/[|\t\n\r]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

/** Serialize verification hits to TSV (tab-separated values). */
export function hitsToTsv(
  hits: VerifiedHit[] | null | undefined,
): string {
  const arr = Array.isArray(hits) ? hits : [];
  const header = TSV_COLUMNS.map((c) => c.header).join("\t");
  const rows = arr.map((h) =>
    TSV_COLUMNS.map((c) => tsvEscape(h[c.key])).join("\t"),
  );
  return [header, ...rows].join("\n") + "\n";
}

/** Serialize verification hits to pretty-printed JSON. */
export function hitsToJson(
  hits: VerifiedHit[] | null | undefined,
): string {
  const arr = Array.isArray(hits) ? hits : [];
  return JSON.stringify(arr, null, 2);
}

/** Create a Blob with the given content and MIME type. */
export function buildDownloadBlob(content: string, mime: string): Blob {
  return new Blob([content], { type: mime });
}

/**
 * Trigger a browser download for the given blob.
 * No-op in environments without DOM (e.g. unit-test jsdom edge cases).
 */
export function downloadBlob(blob: Blob, filename: string): void {
  if (typeof document === "undefined") return;
  if (typeof URL === "undefined" || typeof URL.createObjectURL !== "function") {
    return;
  }
  const a = document.createElement("a");
  const url = URL.createObjectURL(blob);
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/** Sanitized filename prefix helper. */
export function exportFilename(
  segment: string,
  ext: "tsv" | "json",
): string {
  const safe = (segment || "all").replace(/[^a-zA-Z0-9._-]+/g, "_");
  return `verification_${safe}.${ext}`;
}
