import { describe, expect, it } from "vitest";
import { notes, service, serviceLabel, stepLabel, unidentifiedNote } from "./notes";

const w = (code: string, message: string, step_id: string | null = null, details: Record<string, unknown> = {}) => ({
  code,
  message,
  step_id,
  details,
});

describe("service extraction (DATA.md §3.2)", () => {
  it("takes the message prefix before the first ' ('", () => {
    expect(service("blast_nr_protein (timeout after 300s)")).toBe("blast_nr_protein");
    expect(service("plain message")).toBe("plain message");
  });
  it("maps prefixes to display names (COPY.md §3.1)", () => {
    expect(serviceLabel("blast_nr_protein")).toBe("NCBI nr protein");
    expect(serviceLabel("blast_swissprot_protein")).toBe("UniProt");
    expect(serviceLabel("pdb_struct")).toBe("PDB");
    expect(serviceLabel("pubchem_struct")).toBe("PubChem");
    expect(serviceLabel("something_new")).toBe("A database");
  });
});

describe("notes (DATA.md §3)", () => {
  it("merges repeated resolver failures into one note", () => {
    const input = Array.from({ length: 16 }, () => w("identifier_resolver_failed", "blast_nr_protein (timeout)"));
    const { notes: out, hidden } = notes(input);
    expect(out).toHaveLength(1);
    expect(out[0].raw_count).toBe(16);
    expect(out[0].title).toBe("NCBI nr protein search did not finish");
    expect(out[0].severity).toBe("attention");
    expect(hidden).toBe(0);
  });

  it("hides catalogue-hidden codes and na_mode_unsupported misfires", () => {
    const { notes: out, hidden } = notes([
      w("signature_generator_not_applicable", "fingerprint skipped"),
      w("coords_rescaled_nm_to_angstrom", "rescaled"),
      w("identifier_resolver_failed", "blast_nr_protein (na_mode_unsupported)"),
    ]);
    expect(out).toHaveLength(0);
    expect(hidden).toBe(3);
  });

  it("keeps error-severity codes out of the notes list", () => {
    const { notes: out, hidden } = notes([w("worker_lost", "celery worker died")]);
    expect(out).toHaveLength(0);
    expect(hidden).toBe(0);
  });

  it("groups different services into different notes", () => {
    const { notes: out } = notes([
      w("identifier_resolver_failed", "blast_nr_protein (timeout)"),
      w("identifier_resolver_failed", "pubchem_struct (service error)"),
    ]);
    expect(out).toHaveLength(2);
  });

  it("fills affects from details.segment when the backend sends it (G4)", () => {
    const { notes: out } = notes([
      w("verification_failed", "verification failed", "verify_results", { segment: "seg_1" }),
    ]);
    expect(out[0].affects).toEqual(["seg_1"]);
  });

  it("renders render_* prefix codes from the catalogue", () => {
    const { notes: out, hidden } = notes([w("render_png_failed", "pymol crashed")]);
    expect(hidden).toBe(0);
    expect(out[0].severity).toBe("info");
    expect(out[0].title).toBe("Preview image could not be created");
  });

  it("sorts attention before info", () => {
    const { notes: out } = notes([
      w("pbc_unwrap_applied", "unwrapped"),
      w("identifier_resolver_failed", "blast_nr_protein (timeout)"),
    ]);
    expect(out.map((n) => n.severity)).toEqual(["attention", "info"]);
  });

  it("unknown codes become a generic info note with the step label", () => {
    const { notes: out } = notes([w("brand_new_code", "x", "identify_molecules")]);
    expect(out[0].severity).toBe("info");
    expect(out[0].title).toBe("Something unexpected happened during Search databases");
  });
});

describe("stepLabel", () => {
  it("maps task ids and step keys to step labels", () => {
    expect(stepLabel("identify_molecules")).toBe("Search databases");
    expect(stepLabel("analyze_universe")).toBe("Find molecules");
    expect(stepLabel(null)).toBe("the run");
  });
});

describe("unidentifiedNote (DATA.md §3.4)", () => {
  it("summarises missed molecules as one attention note", () => {
    const n = unidentifiedNote(["UNL", "POPC"], ["seg_3", "seg_5"])!;
    expect(n.severity).toBe("attention");
    expect(n.title).toBe("2 molecules were not identified");
    expect(n.affects).toEqual(["seg_3", "seg_5"]);
    expect(n.body).toContain("UNL, POPC");
  });
  it("uses the singular for one molecule", () => {
    expect(unidentifiedNote(["UNL"], ["seg_3"])!.title).toBe("1 molecule was not identified");
  });
  it("is null when everything matched", () => {
    expect(unidentifiedNote([], [])).toBeNull();
  });
});
