import { describe, expect, it } from "vitest";

import { probeStructureGeometry } from "./geometry-check";

const HEADER = "data_x\nloop_\n_atom_site.group_PDB\n";

function atomLine(id: number, x: number, y: number, z: number): string {
  // exporter layout: ATOM <id> <el> <name> . <comp> A ? <seq> ? x y z occ B <auth_seq> <auth_asym> <model>
  return `ATOM ${id} O OH2 . TIP3 A ? ${id} ? ${x.toFixed(3)} ${y.toFixed(3)} ${z.toFixed(3)} 0.0 0.0 ${id} seg_0 1 `;
}

function makeFile(coords: Array<[number, number, number]>): string {
  return HEADER + coords.map((c, i) => atomLine(i + 1, ...c)).join("\n");
}

function scattered(n: number, boxSide: number): Array<[number, number, number]> {
  // deterministic pseudo-scatter (no RNG flakiness in thresholds)
  const out: Array<[number, number, number]> = [];
  for (let i = 0; i < n; i++) {
    out.push([
      ((i * 7919) % 1000) / 1000 * boxSide,
      ((i * 104729) % 1000) / 1000 * boxSide,
      ((i * 1299709) % 1000) / 1000 * boxSide,
    ]);
  }
  return out;
}

describe("probeStructureGeometry", () => {
  it("flags nm-collapsed geometry (a5b785cc shape)", () => {
    // 2000 atoms in a 0.8 A cube == 0.00026 A^3/atom (the real collapse)
    const probe = probeStructureGeometry(makeFile(scattered(2000, 0.8)));
    expect(probe.status).toBe("degenerate");
    expect(probe.densityA3PerAtom).toBeLessThan(1.0);
  });

  it("accepts healthy angstrom geometry", () => {
    // 2000 atoms in an 80 A cube == ~256 A^3/atom — solvated-system shape
    const probe = probeStructureGeometry(makeFile(scattered(2000, 80)));
    expect(probe.status).toBe("ok");
    expect(probe.densityA3PerAtom).toBeGreaterThan(1.0);
  });

  it("does not flag clashy-but-angstrom systems (A003ZR shape)", () => {
    // tight local clashes happen in real systems; global density stays healthy
    const coords = scattered(2000, 80);
    for (let i = 0; i < 500; i++) coords[i] = [40 + i * 0.01, 40, 40]; // crushed blob
    const probe = probeStructureGeometry(makeFile(coords));
    expect(probe.status).toBe("ok");
  });

  it("returns ok for tiny systems (density is meaningless below threshold)", () => {
    const probe = probeStructureGeometry(makeFile(scattered(50, 1)));
    expect(probe.status).toBe("ok");
    expect(probe.atomCount).toBe(50);
  });

  it("returns unknown when nothing parses", () => {
    expect(probeStructureGeometry("not a structure\n").status).toBe("unknown");
  });

  it("returns unknown on malformed coordinate fields instead of misfiring", () => {
    const bad = HEADER + "ATOM 1 O OH2 . TIP3 A ? 1 ? x y z 0.0 0.0 1 seg 1 ";
    expect(probeStructureGeometry(bad).status).toBe("unknown");
  });
});
