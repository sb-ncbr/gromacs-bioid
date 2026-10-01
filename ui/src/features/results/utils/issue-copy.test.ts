import { describe, expect, it } from "vitest";
import { buildIssueCopy } from "./issue-copy";

describe("buildIssueCopy", () => {
  it("signature_generator_failed -> info, generator humanized, design-copy", () => {
    const c = buildIssueCopy(
      "signature_generator_failed",
      "morgan_fingerprint: Generation returned None",
      {},
      false,
    );
    expect(c.severity).toBe("info");
    expect(c.what).toContain("Morgan fingerprint");
    expect(c.what.toLowerCase()).toContain("skipped");
  });

  it("identifier_resolver_failed -> resolver human name + sanitized reason from message", () => {
    const c = buildIssueCopy(
      "identifier_resolver_failed",
      "blast_nr_protein (fasta_resname_protein): BLAST timed out after 300s. Database: /app/databases/nr/nr. Executable: /usr/bin/blastp",
      {},
      false,
    );
    expect(c.what).toContain("BLAST search of the NR protein database");
    expect(c.what).toContain("took too long and was stopped");
    expect(c.what).not.toContain("/app/");
    expect(c.technical).not.toBe("");
    expect(c.technical).not.toContain("/app/");
  });

  it("unknown code falls back gracefully", () => {
    const c = buildIssueCopy("weird_new_code", "something happened", {}, false);
    expect(c.severity).toBe("unknown");
    expect(c.title).toBe("Weird New Code");
  });

  it("critical flag wins over catalog kind", () => {
    const c = buildIssueCopy("load_failed", "No loading strategy succeeded", {}, true);
    expect(c.severity).toBe("critical");
  });
});
