import { describe, expect, it } from "vitest";
import type { Molecule, ViewModel } from "../viewmodel";
import {
  badgeOf,
  bestLine,
  chemRows,
  eyebrow,
  fasta,
  headline,
  moleculeNotes,
  sameAs,
} from "./stageModel";
import navmsRaw from "../viewmodel/fixtures/navms-finished.json";

const navms = navmsRaw as unknown as ViewModel;

const mol = (over: Partial<Molecule>): Molecule => ({
  id: "seg_1",
  display_name: "POPC",
  kind: "lipid",
  chain: null,
  residue_names: ["POPC"],
  copies: 362,
  atoms_per_copy: 134,
  residues_per_copy: null,
  status: "done",
  result: null,
  matches: [],
  more: { verified: 0, related: 0, rejected: 0 },
  descriptor: { smiles: "C", inchikey: "AAA-BBB-C" },
  note_ids: [],
  ...over,
});

describe("eyebrow (COPY.md §2.4)", () => {
  it("chain polymers: label · kind · copies · residues", () => {
    const chainA = navms.molecules[0];
    expect(eyebrow(chainA)).toBe("Chain A · protein · 1 copy · 264 residues");
  });
  it("non-polymers show atoms per copy and the residue name", () => {
    const p = mol({});
    expect(eyebrow(p)).toBe("POPC · lipid · 362 copies · 134 atoms per copy · residue POPC");
  });
  it("uses plural copies and thousand separators", () => {
    const water = mol({ kind: "water", copies: 48004, residue_names: ["SOL"] });
    expect(eyebrow(water)).toContain("48,004 copies");
  });
});

describe("badgeOf (SPEC.md §4)", () => {
  it("words each confidence label with the rounded score", () => {
    const chainA = navms.molecules[0];
    const b = badgeOf(chainA, true);
    expect(b.text).toBe("Medium confidence 78 / 100");
    expect(b.kind).toBe("medium");
  });
  it("exact and none get their own wording, no number", () => {
    const sod = navms.molecules.find((m) => m.display_name === "SOD")!;
    expect(badgeOf(sod, true)).toEqual({ kind: "exact", text: "Exact match", score: null });
    const miss = mol({ result: { state: "not_identified", name: null, description: null, best: null, confidence: null } });
    expect(badgeOf(miss, true).text).toBe("No confident match");
  });
  it("shows the status while running", () => {
    expect(badgeOf(mol({}), false).kind).toBe("status");
  });
});

describe("headline", () => {
  it("uses the hit name with the organism as subtitle (G5 additive)", () => {
    const chainA = navms.molecules[0];
    const h = headline(chainA, true);
    expect(h.title.length).toBeGreaterThan(0);
    expect(h.title).not.toBe("Not identified");
    expect(h.sub).toBeTruthy();
  });
  it("falls back to the best DB+ID when no name exists (G5 gap)", () => {
    const m = mol({
      result: { state: "identified", name: null, description: null, best: { db: "PDB", id: "5HVX", url: "" }, confidence: 88 },
    });
    expect(headline(m, true).title).toBe("PDB 5HVX");
  });
  it("not identified: title + reason", () => {
    const m = mol({ result: { state: "not_identified", name: null, description: null, best: null, confidence: null } });
    const h = headline(m, true);
    expect(h.title).toBe("Not identified");
    expect(h.sub).toBe("No database entry matched this molecule");
  });
});

describe("bestLine", () => {
  it("links the best match; null while running or unidentified", () => {
    const chainA = navms.molecules[0];
    expect(bestLine(chainA, true)!.db).toBe("PDB");
    expect(bestLine(chainA, true)!.url).toContain("http");
    expect(bestLine(chainA, false)).toBeNull();
  });
});

describe("sameAs (SPEC.md §3.5a)", () => {
  it("Chain A is the same as B, C and D", () => {
    const others = sameAs(navms.molecules, navms.molecules[0].id);
    expect(others.map((o) => o.label)).toEqual(["Chain B", "Chain C", "Chain D"]);
  });
  it("is empty for singletons", () => {
    const cla = navms.molecules.find((m) => m.display_name === "CLA")!;
    expect(sameAs(navms.molecules, cla.id)).toEqual([]);
  });
});

describe("fasta / sequence", () => {
  it("wraps at 80 columns with the display name header", () => {
    const chainA = navms.molecules[0];
    const f = fasta(chainA)!;
    expect(f.startsWith(">Chain A\n")).toBe(true);
    const lines = f.trimEnd().split("\n").slice(1);
    expect(lines.every((l) => l.length <= 80)).toBe(true);
    expect(lines.join("")).toBe(chainA.descriptor.sequence);
  });
  it("is null without a sequence", () => {
    expect(fasta(mol({ descriptor: {} }))).toBeNull();
  });
});

describe("chemRows (COPY.md §2.4 order)", () => {
  it("renders only available fields in the fixed order", () => {
    const rows = chemRows(mol({ descriptor: { element: "P", formula: "C42H82NO8P", smiles: "C", inchikey: "K" } }));
    expect(rows.map((r) => r.label)).toEqual([
      "Element", "Formula", "SMILES", "InChIKey", "Residue names", "Atoms per copy",
    ]);
    expect(rows.find((r) => r.label === "SMILES")!.copiable).toBe(true);
    expect(rows.find((r) => r.label === "Residue names")!.value).toBe("POPC");
  });
  it("empty descriptor with no residue names yields no rows", () => {
    expect(chemRows(mol({ descriptor: {}, residue_names: [], atoms_per_copy: 0 }))).toEqual([]);
  });
});

describe("moleculeNotes", () => {
  it("selects notes by id and by affects", () => {
    const m = mol({ note_ids: ["n1"] });
    const all: import("../viewmodel").Note[] = [
      { id: "n1", severity: "attention", code: "c", title: "t", body: "b", action: null, affects: [], raw_count: 1 },
      { id: "n2", severity: "info", code: "c", title: "t2", body: "b", action: null, affects: ["seg_1"], raw_count: 2 },
      { id: "n3", severity: "info", code: "c", title: "t3", body: "b", action: null, affects: [], raw_count: 1 },
    ];
    expect(moleculeNotes(m, all).map((n) => n.id)).toEqual(["n1", "n2"]);
  });
});
