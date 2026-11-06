/**
 * Client-side geometry sanity gate for mmCIF structure text.
 *
 * Why this exists (run a5b785cc, 2026-10-21): coordinates arriving in
 * nanometres collapse the system ~10x; Mol* then infers astronomically many
 * distance-based bonds and blocks the main thread until the tab dies — the
 * 25 s watchdog in the viewer cannot fire because the load itself never
 * yields. The only safe answer is to NOT engage Mol* on degenerate input.
 *
 * Evidence behind the threshold (Phase-0 measurements):
 *   collapsed system (a5b785cc):  0.016 A^3/atom
 *   healthy systems (gro/pdb):    10.2 – 36.9 A^3/atom
 *   clashy-but-valid systems:     ~25 A^3/atom (density alone is clash-safe)
 * A cutoff of 1.0 A^3/atom sits ~60x below the healthy band and ~60x above
 * the observed collapse — no legitimate system comes close to tripping it.
 *
 * The check is a single streaming pass over the mmCIF ATOM/HETATM records:
 * atom count + per-axis min/max. No Mol*, no main-thread-heavy work
 * (~100 ms for a 5 MB file).
 */

export const DENSITY_MIN_A3_PER_ATOM = 1.0;
export const MIN_ATOMS_FOR_DENSITY = 100;

export type GeometryStatus = "ok" | "degenerate" | "unknown";

export interface GeometryProbe {
  status: GeometryStatus;
  atomCount: number;
  /** A^3 per atom when computable, else null. */
  densityA3PerAtom: number | null;
  /** Per-axis bounding-box span, null when no atoms parsed. */
  span: [number, number, number] | null;
}

const ATOM_RECORD = /^(?:ATOM|HETATM)\s/;

/** Probe mmCIF/structure text for collapse-grade degeneracy. */
export function probeStructureGeometry(text: string): GeometryProbe {
  let count = 0;
  let minX = Infinity,
    minY = Infinity,
    minZ = Infinity,
    maxX = -Infinity,
    maxY = -Infinity,
    maxZ = -Infinity;

  for (const line of text.split("\n")) {
    if (!ATOM_RECORD.test(line)) continue;
    // mmCIF atom_site order written by our exporter:
    // id type label_alt? … Cartn_x(10) Cartn_y(11) Cartn_z(12) — but be liberal:
    // split on whitespace and read the three floats preceding the last 4-5
    // occupancy/B-factor/auth fields. Our exporter's layout is fixed, so the
    // simple positional read holds; fall through to 'unknown' on parse trouble.
    const parts = line.trim().split(/\s+/);
    if (parts.length < 13) return { status: "unknown", atomCount: count, densityA3PerAtom: null, span: null };
    const x = Number(parts[10]);
    const y = Number(parts[11]);
    const z = Number(parts[12]);
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) {
      return { status: "unknown", atomCount: count, densityA3PerAtom: null, span: null };
    }
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (z < minZ) minZ = z;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
    if (z > maxZ) maxZ = z;
    count++;
  }

  if (count === 0) {
    return { status: "unknown", atomCount: 0, densityA3PerAtom: null, span: null };
  }
  const span: [number, number, number] = [maxX - minX, maxY - minY, maxZ - minZ];
  if (count < MIN_ATOMS_FOR_DENSITY) {
    // too few atoms for density to mean anything — let the viewer try
    return { status: "ok", atomCount: count, densityA3PerAtom: null, span };
  }
  const density = (span[0] * span[1] * span[2]) / count;
  return {
    status: density < DENSITY_MIN_A3_PER_ATOM ? "degenerate" : "ok",
    atomCount: count,
    densityA3PerAtom: density,
    span,
  };
}
