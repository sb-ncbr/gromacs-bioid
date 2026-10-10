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
