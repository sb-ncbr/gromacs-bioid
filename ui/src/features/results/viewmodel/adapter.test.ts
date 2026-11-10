import { describe, expect, it } from "vitest";
import { adapt, type ApiBundle } from "./adapter";

const NOW = Date.parse("2026-10-26T12:00:00Z");
const ISO = (h: number, m = 0) => `2026-10-26T${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:00Z`;

const SEGMENTS = ["seg_0_Protein_chain_A", "seg_1_Protein_chain_B", "seg_5_POPC", "seg_9_SOD", "seg_10_SOD"];

function baseBundle(): ApiBundle {
  return {
    runId: "9d90d777-abcd-ef01",
    summary: { status: "running", started_at: ISO(10), input_kind: "gromacs" },
    status: {
      tasks: [
        "discover_input",
        "load_simulation",
        "repair_topology",
        "unwrap_periodic_boundaries",
        "analyze_universe",
        "generate_signatures",
      ].map((task_id) => ({ task_id, status: "success", started_at: ISO(10), finished_at: ISO(10, 1) })),
      warnings: [],
    },
    molecules: {
      segments: SEGMENTS,
      segment_meta: {
        seg_0_Protein_chain_A: { type: "protein", atom_count: 2000, residue_count: 264 },
        seg_1_Protein_chain_B: { type: "protein", atom_count: 2000, residue_count: 264 },
        seg_5_POPC: { type: "lipid", atom_count: 130 },
        seg_9_SOD: { type: "ion", atom_count: 1 },
        seg_10_SOD: { type: "ion", atom_count: 1 },
      },
    },
    signatures: {
      signatures: [
        { segment: "seg_0_Protein_chain_A", generator: "fasta_map_protein", signature: ">chain A\nMKTEST\nSEQ\n" },
        { segment: "seg_9_SOD", generator: "atom", signature: { element: "Na" } },
        { segment: "seg_5_POPC", generator: "smiles", signature: { smiles: "C(CC)OC" } },
        { segment: "seg_5_POPC", generator: "resname", signature: ["POPC"] },
      ],
    },
    verification: null,
    queue: null,
    files: { files: ["navms_input.tpr", "frame.gro"] },
  };
}

describe("adapt · running run (G2 fallback)", () => {
  const bundle = baseBundle();
  bundle.status!.tasks!.push({ task_id: "identify_molecules", status: "running", started_at: ISO(11, 58), finished_at: null });
  bundle.status!.warnings = [
    ...Array.from({ length: 16 }, () => ({ code: "identifier_resolver_failed", message: "blast_nr_protein (timeout)", step_id: "identify_molecules", details: {} })),
    { code: "coords_rescaled_nm_to_angstrom", message: "rescaled", step_id: null, details: {} },
  ];
  const vm = adapt(bundle, { now: NOW });

  it("keeps the run live with the search step active", () => {
    expect(vm.run.status).toBe("running");
    expect(vm.progress.stages.find((s) => s.key === "search")!.status).toBe("active");
    expect(vm.run.elapsed_s).toBe(7200);
  });

  it("falls back to the first input file as the run name (gap G1)", () => {
    expect(vm.run.name).toBe("navms_input.tpr");
    expect(vm.run.input.format).toBe("GROMACS");
    expect(vm.run.input.files).toEqual(["navms_input.tpr", "frame.gro"]);
  });

  it("derives molecule names and disambiguates duplicates (DATA.md §2)", () => {
    expect(vm.molecules.map((m) => m.display_name)).toEqual([
      "Chain A",
      "Chain B",
      "POPC",
      "SOD (ion)",
      "SOD (ion)",
    ]);
    expect(vm.molecules[0].chain).toBe("A");
    expect(vm.run.input.atoms).toBe(4132);
  });

  it("marks molecules searching while the search step runs, no results yet", () => {
    expect(vm.molecules.every((m) => m.status === "searching")).toBe(true);
    expect(vm.molecules.every((m) => m.result === null)).toBe(true);
  });

  it("groups the 16 BLAST timeouts into one note and counts hidden messages", () => {
    const resolver = vm.notes.find((n) => n.code === "identifier_resolver_failed")!;
    expect(resolver.raw_count).toBe(16);
    expect(resolver.title).toBe("NCBI nr protein search did not finish");
    expect(vm.hidden_note_count).toBe(1);
  });

  it("ships JSON-only downloads until gap G6 lands", () => {
    expect(vm.downloads).toEqual([{ key: "json", label: "All results (JSON)", primary: true }]);
  });

  it("fills the descriptor from signatures", () => {
    expect(vm.molecules[0].descriptor.sequence).toBe("MKTESTSEQ");
    expect(vm.molecules[2].descriptor.smiles).toBe("C(CC)OC");
    expect(vm.molecules[3].descriptor.element).toBe("Na");
    expect(vm.molecules[2].residue_names).toEqual(["POPC"]);
  });
});

describe("adapt · queued run", () => {
  const bundle = baseBundle();
  bundle.queue = { state: "queued", ahead: 2, position: 3 };
  const vm = adapt(bundle, { now: NOW });

  it("reports queued with the queue position", () => {
    expect(vm.run.status).toBe("queued");
    expect(vm.progress.queue_position).toBe(2);
    expect(vm.run.elapsed_s).toBeNull();
  });
});

describe("adapt · finished run", () => {
  const bundle = baseBundle();
  bundle.summary = { status: "success", started_at: ISO(10), finished_at: ISO(11, 35), input_kind: "gromacs" };
  bundle.status!.tasks!.push(
    { task_id: "identify_molecules", status: "success", started_at: ISO(10, 30), finished_at: ISO(11) },
    { task_id: "verify_results", status: "success", started_at: ISO(11), finished_at: ISO(11, 20) },
    { task_id: "export_results", status: "success", started_at: ISO(11, 20), finished_at: ISO(11, 35) },
  );
  bundle.verification = [
    {
      segment: "seg_0_Protein_chain_A",
      hits: [
        { identifier: "8VQR", database: "pdb", final_confidence: 85, is_verified: true, database_url: "https://rcsb.org/structure/8VQR", similarity_score: 0.955, name: "ATPase alpha-1", organism: "Homo sapiens" },
        { identifier: "2BBC", database: "pdb", final_confidence: 78, is_verified: true, similarity_score: 0.87 },
        { identifier: "1IMO", database: "pdb", final_confidence: 30, is_verified: false, rejection_reason: "alignment identity below 30%" },
      ],
    },
    {
      segment: "seg_1_Protein_chain_B",
      hits: [{ identifier: "2BBC", database: "pdb", final_confidence: 30, is_verified: true }],
    },
    {
      segment: "seg_9_SOD",
      hits: [{ identifier: "NA", database: "element", final_confidence: 50, is_verified: true, database_url: "" }],
    },
    {
      segment: "seg_5_POPC",
      hits: [{ identifier: "43", database: "pubchem_cid", final_confidence: 20, is_verified: false, rejection_reason: "different chemical formula" }],
    },
  ];
  const vm = adapt(bundle, { now: NOW });

  it("is finished with all steps done", () => {
    expect(vm.run.status).toBe("finished");
    expect(vm.run.elapsed_s).toBe(5700);
    expect(vm.progress.stages.every((s) => s.status === "done")).toBe(true);
  });

  it("builds the identified result with best match, name and matches (G5 additive)", () => {
    const a = vm.molecules[0];
    expect(a.status).toBe("done");
    expect(a.result!.state).toBe("identified");
    expect(a.result!.name).toBe("ATPase alpha-1");
    expect(a.result!.description).toBe("Homo sapiens");
    expect(a.result!.best).toEqual({ db: "PDB", id: "8VQR", url: "https://rcsb.org/structure/8VQR" });
    expect(a.result!.confidence).toBe(85);
    expect(a.matches).toHaveLength(1);
    expect(a.matches[0].evidence).toBe("87% sequence identity");
    expect(a.more).toEqual({ verified: 2, related: 0, rejected: 1 });
  });

  it("derives lead, exact and not-identified states", () => {
    expect(vm.molecules[1].result!.state).toBe("lead");
    const sod = vm.molecules[3];
    expect(sod.result!.state).toBe("exact");
    expect(sod.result!.confidence).toBeNull();
    expect(vm.molecules[2].result!.state).toBe("not_identified");
    expect(vm.molecules[4].result!.state).toBe("not_identified");
  });

  it("adds the derived not-identified note first (SPEC.md ordering)", () => {
    expect(vm.notes[0].id).toBe("derived:not_identified");
    // chain B (lead) + POPC + second SOD (no verification entry)
    expect(vm.notes[0].raw_count).toBe(3);
    expect(vm.molecules[2].note_ids).toContain("derived:not_identified");
  });
});

describe("adapt · failed run", () => {
  const bundle = baseBundle();
  bundle.summary = { status: "failed", started_at: ISO(10), finished_at: ISO(10, 47) };
  bundle.status!.tasks!.push({ task_id: "identify_molecules", status: "failed", started_at: ISO(10, 30), finished_at: ISO(10, 47) });
  bundle.status!.critical_errors = [{ code: "worker_lost", message: "celery worker died", critical: true }];
  const vm = adapt(bundle, { now: NOW });

  it("surfaces the error banner from the catalogue", () => {
    expect(vm.run.status).toBe("failed");
    expect(vm.error!.title).toBe("The processing server stopped unexpectedly");
    expect(vm.error!.action).toContain("9d90d777");
    expect(vm.error!.technical).toContain("worker_lost");
    expect(vm.progress.stages.find((s) => s.key === "search")!.status).toBe("failed");
  });

  it("marks molecules not searched", () => {
    expect(vm.molecules.every((m) => m.status === "not_searched")).toBe(true);
  });
});

describe("adapt · gap switches", () => {
  it("adds the CSV download when gap G6 lands", () => {
    const vm = adapt(baseBundle(), { csvAvailable: true });
    expect(vm.downloads[0]).toEqual({ key: "csv", label: "Results table (CSV)", primary: true });
  });
  it("uses G2 progress when the backend sends it", () => {
    const bundle = baseBundle();
    bundle.status!.progress = { molecules_done: 6, molecules_total: 10 };
    const vm = adapt(bundle, {});
    expect(vm.progress.molecules_done).toBe(6);
    expect(vm.progress.molecules_total).toBe(10);
  });
  it("uses G1/G3 additive fields when present", () => {
    const bundle = baseBundle();
    bundle.summary!.run_name = "My NavMs test";
    bundle.molecules!.segment_meta!.seg_5_POPC = { type: "lipid", atom_count: 130, copies: 278, display_name: "POPC" };
    const vm = adapt(bundle, {});
    expect(vm.run.name).toBe("My NavMs test");
    expect(vm.molecules[2].copies).toBe(278);
    expect(vm.run.input.atoms).toBe(2000 + 2000 + 130 * 278 + 1 + 1);
  });
});

describe("inputFilesOf · header lists submitted inputs only", () => {
  it("keeps the input/ directory of a run listing (live run bce4a0fa)", async () => {
    const { inputFilesOf } = await import("./adapter");
    const listing = ["config.ini", "input/MDR00042100.gro", "input/MDR00042100.tpr",
      "results.debug.log", "results.json", "results.log", "seg_0_PROA.mmcif", "system.mmcif"];
    expect(inputFilesOf(listing)).toEqual(["input/MDR00042100.gro", "input/MDR00042100.tpr"]);
  });
  it("drops known outputs from a flat listing", async () => {
    const { inputFilesOf } = await import("./adapter");
    expect(inputFilesOf(["navms_input.tpr", "frame.gro", "results.json", "system.mmcif", "config.ini"]))
      .toEqual(["navms_input.tpr", "frame.gro"]);
  });
});

describe("failed run: unreached molecules are not searched, not unidentified", () => {
  it("keeps result null without hits when the run failed", () => {
    const vm = adapt({
      runId: "fdd4641a-0000",
      summary: { status: "failed" },
      status: { pipeline: { status: "failed" }, tasks: [], warnings: [], critical_errors: [] },
      molecules: { segments: ["A_1"], segment_meta: { A_1: { type: "protein", display_name: "A_1" } } },
      signatures: null,
      verification: [],
      queue: null,
      files: null,
    });
    expect(vm.molecules[0].result).toBeNull();
    expect(vm.notes.some((n) => n.code === "derived_not_identified")).toBe(false);
  });
});

describe("running run: rows follow per-segment progress (G2)", () => {
  it("uses progress.per_segment over the step-level guess", () => {
    const vm = adapt({
      runId: "8338ea32-0000",
      summary: { status: "running" },
      status: {
        pipeline: { status: "running" },
        tasks: [{ task_id: "identify_molecules", status: "running" } as never],
        warnings: [],
        critical_errors: [],
        progress: { molecules_done: 1, molecules_total: 2, per_segment: { a: "searched", b: "searching" } },
      },
      molecules: { segments: ["a", "b"], segment_meta: { a: { type: "protein" }, b: { type: "lipid" } } },
      signatures: null,
      verification: null,
      queue: null,
      files: null,
    });
    expect(vm.molecules.map((m) => m.status)).toEqual(["searched", "searching"]);
  });
});

describe("run status comes from the polled status first", () => {
  it("finished status beats a stale running summary", () => {
    const vm = adapt({
      runId: "6b21b4ec-0000",
      summary: { status: "running" },
      status: { pipeline: { status: "success" }, tasks: [], warnings: [], critical_errors: [] },
      molecules: { segments: [], segment_meta: {} },
      signatures: null,
      verification: [],
      queue: null,
      files: null,
    });
    expect(vm.run.status).toBe("finished");
  });
});

describe("sequence for nucleic acids", () => {
  it("reads fasta_map_nucleic when there is no protein sequence", () => {
    const vm = adapt({
      runId: "6b21b4ec-0000",
      summary: { status: "success" },
      status: { pipeline: { status: "success" }, tasks: [], warnings: [], critical_errors: [] },
      molecules: { segments: ["SYSTEM__v1"], segment_meta: { SYSTEM__v1: { type: "nucleic" } } },
      signatures: { signatures: [{ segment: "SYSTEM__v1", generator: "fasta_map_nucleic", signature: "TGCTTATCAATTTGTTGCA" }] },
      verification: [],
      queue: null,
      files: null,
    });
    expect(vm.molecules[0].descriptor.sequence).toBe("TGCTTATCAATTTGTTGCA");
  });
});

describe("sequence for multi-chain molecules", () => {
  // run 4bc17f8d (CYS): one sequence per chain, chains B-D unreadable ("X")
  const vm = adapt({
    runId: "4bc17f8d-0000",
    summary: { status: "success" },
    status: { pipeline: { status: "success" }, tasks: [], warnings: [], critical_errors: [] },
    molecules: { segments: ["CYS"], segment_meta: { CYS: { type: "protein" } } },
    signatures: {
      signatures: [
        { segment: "CYS", generator: "fasta_map_protein[A]", signature: "CPFGEVFNAT" },
        { segment: "CYS", generator: "fasta_map_protein[B]", signature: "X" },
        { segment: "CYS", generator: "fasta_map_protein[C]", signature: "MKTAYIAKQR" },
        { segment: "CYS", generator: "fasta_resname_protein[A]", signature: "CPFGEVFNAT" },
      ],
    },
    verification: [],
    queue: null,
    files: null,
  });

  it("reads the per-chain sequences and drops unreadable chains", () => {
    const d = vm.molecules[0].descriptor;
    expect(d.sequence).toBe("CPFGEVFNAT");
    expect(d.chains).toEqual([
      { label: "A", sequence: "CPFGEVFNAT" },
      { label: "C", sequence: "MKTAYIAKQR" },
    ]);
  });
});
