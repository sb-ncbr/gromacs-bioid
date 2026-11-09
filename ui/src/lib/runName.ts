/**
 * Run names may carry a description after ">" ("Title>Description"), the
 * convention the API's /runs/examples parses (parse_run_title) for the
 * landing cards. Pages show the title; the description is a subtitle.
 */
export function splitRunName(name: string | null | undefined): { title: string; description: string | null } {
  const raw = (name ?? "").trim();
  const i = raw.indexOf(">");
  if (i === -1) return { title: raw, description: null };
  return { title: raw.slice(0, i).trim(), description: raw.slice(i + 1).trim() || null };
}
