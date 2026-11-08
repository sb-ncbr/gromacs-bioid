/**
 * File-type helpers for the frontpage upload flow.
 * Engine matrix (2026-10 loading-strategy widening): keep in sync with
 * src_new loader — GROMACS, AMBER, CHARMM/NAMD, LAMMPS, PDB, mmCIF.
 */

/** Accepted extensions, used for the UI hint. */
export const ACCEPTED_EXTENSIONS = [
  // GROMACS
  "tpr", "gro", "top", "itp", "trr", "xtc",
  // AMBER
  "prmtop", "parm7", "nc", "rst7", "inpcrd", "restrt", "mdcrd",
  // CHARMM / NAMD
  "psf", "pdb", "crd", "dcd",
  // LAMMPS
  "data",
  // mmCIF
  "cif",
  // config + archives
  "json", "yaml", "yml", "zip", "tar", "ini",
] as const;

/** react-dropzone `accept` map (mime type -> extension list). */
export const ACCEPT_MAP: Record<string, string[]> = {
  "application/octet-stream": [
    ".tpr", ".gro", ".top", ".itp", ".trr", ".xtc",
    ".prmtop", ".parm7", ".nc", ".rst7", ".inpcrd", ".restrt", ".mdcrd",
    ".psf", ".pdb", ".crd", ".dcd",
    ".data", ".cif",
  ],
  "application/json": [".json"],
  "text/yaml": [".yaml", ".yml"],
  "application/x-yaml": [".yaml", ".yml"],
  "application/zip": [".zip"],
  "application/x-tar": [".tar"],
  "application/gzip": [".tar.gz"],
  "text/plain": [".ini"],
};

const ACCEPTED = new Set<string>([...ACCEPTED_EXTENSIONS, "tar.gz", "tgz"]);

/**
 * Extension check. The `accept` map alone is not enough: react-dropzone also
 * accepts any file whose MIME type matches a key, so text/plain (for .ini)
 * let a notes.txt through.
 */
export function isAccepted(name: string): boolean {
  return ACCEPTED.has(fileExtension(name).toLowerCase());
}

/**
 * Non-blocking hints for an input set that is missing its other half
 * (the loader decides; this only saves a failed run).
 */
export function inputHints(names: string[]): string[] {
  const ext = new Set(names.map((n) => fileExtension(n).toLowerCase()));
  const has = (...e: string[]) => e.some((x) => ext.has(x));
  if (has("zip", "tar", "tar.gz", "tgz")) return [];
  const hints: string[] = [];
  const coords = has("gro", "pdb", "cif", "crd", "rst7", "inpcrd", "restrt", "nc", "mdcrd", "dcd", "xtc", "trr");
  if (has("top") && !has("tpr") && !coords) hints.push("A .top needs coordinates: add the .gro.");
  if (has("itp") && !has("top", "tpr")) hints.push(".itp files are includes: add the .top that includes them, or the .tpr.");
  if (has("prmtop", "parm7") && !has("rst7", "inpcrd", "restrt", "nc", "mdcrd", "pdb")) hints.push("An AMBER topology needs coordinates: add the .rst7 or .inpcrd.");
  if (has("psf") && !has("pdb", "crd", "dcd", "cif")) hints.push("A .psf needs coordinates: add the .pdb or .crd.");
  if (has("rst7", "inpcrd", "restrt", "mdcrd", "nc") && !has("prmtop", "parm7")) hints.push("AMBER coordinates need their topology: add the .prmtop.");
  if (has("xtc", "trr") && !has("tpr", "top", "gro", "pdb")) hints.push("A trajectory alone has no topology: add the .tpr (or .top and .gro).");
  return hints;
}

/** Return the last extension segment, handling `.tar.gz` as one unit. */
export function fileExtension(name: string): string {
  const base = name.toLowerCase();
  if (base.endsWith(".tar.gz")) return "tar.gz";
  const parts = name.split(".");
  return parts.length > 1 ? parts[parts.length - 1] : "";
}

/** Truncate a file name to `max` chars while preserving its extension. */
export function truncateFileName(name: string, max = 35): string {
  if (name.length <= max) return name;
  const ext = fileExtension(name);
  const stem = ext ? name.slice(0, -(ext.length + 1)) : name;
  const cut = Math.max(0, max - ext.length - 4);
  return stem.slice(0, cut) + "…" + (ext ? "." + ext : "");
}
