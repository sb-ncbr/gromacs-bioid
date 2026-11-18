import { describe, expect, it } from "vitest";
import type { ServiceRow } from "../../lib/api/admin";
import { errorBreakdown, errorTone, formatSeconds, rowsFor, serviceLabel } from "./services";

function row(service: string, stage: string, calls: number, errors: number, extra: Partial<ServiceRow> = {}): ServiceRow {
  return {
    service, stage, calls, cached: 0, errors, error_share: calls ? errors / calls : null, retries: 0,
    outcomes: { ok: calls - errors, http_5xx: errors }, mean_s: 1, p50_s: 1, p95_s: 3, ...extra,
  };
}

describe("services", () => {
  it("labels databases and web hosts", () => {
    expect(serviceLabel("db:chembl_struct@sim")).toEqual({ kind: "database", name: "chembl_struct (similar)" });
    expect(serviceLabel("db:blast_nr_protein")).toEqual({ kind: "database", name: "blast_nr_protein" });
    expect(serviceLabel("http:www.ebi.ac.uk")).toEqual({ kind: "web", name: "www.ebi.ac.uk" });
  });

  it("filters one stage or merges every stage per service", () => {
    const rows = [
      row("http:rest.uniprot.org", "identify_molecules", 10, 0, { p95_s: 1 }),
      row("http:rest.uniprot.org", "verify_results", 30, 6, { p95_s: 10, mean_s: 3 }),
      row("http:data.rcsb.org", "verify_results", 5, 0),
    ];
    expect(rowsFor(rows, "verify").map((r) => r.service)).toEqual(["http:rest.uniprot.org", "http:data.rcsb.org"]);
    expect(rowsFor(rows, "identify")).toHaveLength(1);
    const [uniprot] = rowsFor(rows, "all");
    expect(uniprot.calls).toBe(40);
    expect(uniprot.errors).toBe(6);
    expect(uniprot.error_share).toBeCloseTo(0.15);
    expect(uniprot.p95_s).toBe(10);
    expect(uniprot.mean_s).toBeCloseTo((1 * 10 + 3 * 30) / 40);
    expect(uniprot.outcomes.http_5xx).toBe(6);
  });

  it("tones error shares like the alarm", () => {
    expect(errorTone(0.6, 12)).toBe("error");
    expect(errorTone(0.6, 5)).toBe("warn");
    expect(errorTone(0.01, 100)).toBe("ok");
    expect(errorTone(null, 0)).toBe("muted");
  });

  it("formats seconds and error breakdowns", () => {
    expect(formatSeconds(0.12)).toBe("0.1 s");
    expect(formatSeconds(4)).toBe("4 s");
    expect(formatSeconds(90)).toBe("1.5 min");
    expect(formatSeconds(7200)).toBe("2 h");
    expect(formatSeconds(Infinity)).toBe("> 12 h");
    expect(errorBreakdown({ ok: 5, "error:timeout": 2, http_5xx: 7, cache_shared: 1 })).toBe("http_5xx 7, timeout 2");
  });
});
