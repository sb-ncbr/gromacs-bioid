/**
 * Helpers for deriving the "uploaded input" file list.
 *
 * Primary source: `status.pipeline.input_files` keys (server-provided).
 * Fallback: derive from the flat run file list (entries under `input/`).
 */

/**
 * Derive input file paths from the flat run file list.
 *
 * Rules:
 *  - Must start with `input/`
 *  - Exclude nested directories beyond `input/` (e.g. `input/sub/x.gro`)
 *  - Exclude temporary JSON files matching `tmp*.json`
 */
export function deriveInputFiles(files: string[]): string[] {
  return files.filter((f) => {
    if (!f.startsWith("input/")) return false;
    const rest = f.slice("input/".length);
    if (!rest) return false;
    // Exclude nested directories beyond input/
    if (rest.includes("/")) return false;
    // Exclude tmp*.json
    if (/^tmp.*\.json$/i.test(rest)) return false;
    return true;
  });
}
