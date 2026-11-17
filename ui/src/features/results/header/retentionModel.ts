/**
 * The run's expiry line (2026-11-17): when the run is deleted, and which
 * "keep longer" choices its owner has. Pure, for tests; RetentionLine.tsx
 * renders it.
 */

export interface RetentionInfo {
  policy: string;
  days?: number | null;
  expires_at?: string | null;
  example?: boolean;
  owner_choices?: number[];
}

export interface RetentionView {
  text: string;
  /** Deleted within a week: shown with emphasis. */
  soon: boolean;
  /** Days the owner can still choose (each extends the expiry). */
  choices: number[];
}

const DAY_MS = 86_400_000;

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function retentionView(r: RetentionInfo | null | undefined, now: number = Date.now()): RetentionView | null {
  if (!r) return null;
  if (r.example) return { text: "This is an example run: it is kept permanently.", soon: false, choices: [] };
  if (!r.expires_at) {
    return r.policy === "preserve"
      ? { text: "These results are kept permanently.", soon: false, choices: [] }
      : null; // not finished yet: no expiry to show
  }
  const expires = new Date(r.expires_at).getTime();
  const daysLeft = Math.max(0, Math.ceil((expires - now) / DAY_MS));
  const when = daysLeft === 0 ? "today" : daysLeft === 1 ? "tomorrow" : `in ${daysLeft} days`;
  return {
    text: `Kept until ${formatDate(r.expires_at)} (${when}), then deleted. Download results.json to keep a copy.`,
    soon: daysLeft <= 7,
    choices: (r.owner_choices ?? []).filter((d) => now + d * DAY_MS > expires),
  };
}
