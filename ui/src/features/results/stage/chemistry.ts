/**
 * Average molecular mass from a formula (2026-11-17), for molecules BioID
 * could not identify: the backend computes the formula, not the mass.
 * Standard atomic weights (IUPAC 2021, abridged); null for an element not
 * listed or a formula that does not parse.
 */
const WEIGHTS: Record<string, number> = {
  H: 1.008, B: 10.81, C: 12.011, N: 14.007, O: 15.999, F: 18.998, Na: 22.99, Mg: 24.305,
  Al: 26.982, Si: 28.085, P: 30.974, S: 32.06, Cl: 35.45, K: 39.098, Ca: 40.078, Mn: 54.938,
  Fe: 55.845, Co: 58.933, Ni: 58.693, Cu: 63.546, Zn: 65.38, Se: 78.971, Br: 79.904, Rb: 85.468,
  Sr: 87.62, Mo: 95.95, Cd: 112.41, I: 126.9, Cs: 132.91, Ba: 137.33, Li: 6.94, Pt: 195.08,
};

export function formulaMass(formula: string | null | undefined): number | null {
  if (!formula) return null;
  const clean = formula.replace(/[+-]\d*$/, "");
  const parts = [...clean.matchAll(/([A-Z][a-z]?)(\d*)/g)];
  if (parts.length === 0 || parts.map((p) => p[0]).join("") !== clean) return null;
  let mass = 0;
  for (const [, el, n] of parts) {
    const w = WEIGHTS[el];
    if (w === undefined) return null;
    mass += w * (n ? Number(n) : 1);
  }
  return mass;
}
