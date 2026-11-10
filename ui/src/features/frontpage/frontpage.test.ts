import { describe, expect, it } from "vitest";
import {
  ACCEPTED_EXTENSIONS,
  ACCEPT_MAP,
  fileExtension,
  truncateFileName,
} from "./fileTypes";
import {
  activePresetId,
  applyPreset,
  buildRunFormData,
  configDiff,
  humanLabel,
  identifierGroups,
  parseConfigOptions,
  resolveConfigToPost,
  type RunPreset,
  shouldRequireNonNegative,
  validateNumberInput,
  type RunConfig,
  normalizedWeights,
  FIELD_HELP,
} from "./config";
import {
  formatCreated,
  queueChipText,
  runTitle,
  statusStyle,
} from "./status";

const SAMPLE: RunConfig = {
  identifiers: { blast_nt: true, blast_nt_similarity: true, name_ccd: true, foo: true },
  verification: { tm_score_threshold: 0.5, min_final_confidence: 0.0, verify_top_n: 100 },
};

const QUICK: RunPreset = {
  id: "quick",
  title: "Quick look",
  description: "",
  icon: "zap",
  overrides: { identifiers: { blast_nt: false, blast_nt_similarity: false }, verification: { verify_top_n: 30 } },
};
const BALANCED: RunPreset = { id: "balanced", title: "Balanced", description: "", icon: "scale", overrides: {} };

describe("fileTypes", () => {
  it("fileExtension handles tar.gz and plain exts", () => {
    expect(fileExtension("sim.tar.gz")).toBe("tar.gz");
    expect(fileExtension("system.pdb")).toBe("pdb");
    expect(fileExtension("config.ini")).toBe("ini");
    expect(fileExtension("noext")).toBe("");
  });

  it("truncateFileName preserves the extension", () => {
    expect(truncateFileName("short.pdb")).toBe("short.pdb");
    const long = "a-very-long-membrane-simulation-structure-file.pdb";
    const out = truncateFileName(long, 35);
    expect(out.length).toBeLessThanOrEqual(35);
    expect(out.endsWith(".pdb")).toBe(true);
    expect(out).toContain("…");
  });

  it("ACCEPT_MAP covers the engine matrix + legacy config/archives", () => {
    for (const ext of [
      "tpr", "gro", "top", "itp", "trr", "xtc",
      "prmtop", "parm7", "nc", "rst7", "inpcrd", "restrt", "mdcrd",
      "psf", "pdb", "crd", "dcd", "data", "cif",
      "json", "yaml", "yml", "zip", "tar", "ini",
    ]) {
      expect(ACCEPTED_EXTENSIONS).toContain(ext);
    }
    expect(ACCEPT_MAP["application/octet-stream"]).toEqual([
      ".tpr", ".gro", ".top", ".itp", ".trr", ".xtc",
      ".prmtop", ".parm7", ".nc", ".rst7", ".inpcrd", ".restrt", ".mdcrd",
      ".psf", ".pdb", ".crd", ".dcd",
      ".data", ".cif",
    ]);
  });
});

describe("config: non-negative rules", () => {  it("bounds fields whose names imply a floor", () => {
    expect(shouldRequireNonNegative("global_timeout_s")).toBe(true);
    expect(shouldRequireNonNegative("tm_score_threshold")).toBe(true);
    expect(shouldRequireNonNegative("verify_top_n")).toBe(true);
    expect(shouldRequireNonNegative("signatures_parallel")).toBe(false);
    expect(shouldRequireNonNegative("smiles")).toBe(false);
  });
});

describe("config: validateNumberInput", () => {
  it("rejects empty input and keeps the previous value", () => {
    const r = validateNumberInput("", 5, "n_threads");
    expect(r.ok).toBe(false);
    expect(r.value).toBe(5);
  });

  it("rejects non-numeric input", () => {
    expect(validateNumberInput("abc", 5, "n").ok).toBe(false);
  });

  it("rejects negative values for bounded fields", () => {
    const r = validateNumberInput("-3", 5, "global_timeout_s");
    expect(r.ok).toBe(false);
    expect(r.value).toBe(5);
    expect(r.error).toBeTruthy();
  });

  it("accepts negative values for unbounded fields", () => {
    const r = validateNumberInput("-1", 5, "smiles");
    expect(r.ok).toBe(true);
    expect(r.value).toBe(-1);
  });

  it("accepts valid numbers (incl. floats)", () => {
    expect(validateNumberInput("10", 0, "n")).toEqual({ ok: true, value: 10, display: "10" });
    expect(validateNumberInput("2.5", 0, "element_mass_tolerance").value).toBe(2.5);
  });
});

describe("config: humanLabel", () => {
  it("title-cases snake_case keys", () => {
    expect(humanLabel("blast_pdb_protein")).toBe("BLAST PDB protein");
    expect(humanLabel("global_timeout_s")).toBe("Global timeout (s)");
    expect(humanLabel("tpr_resid_from_one")).toBe("TPR resid from one");
    expect(humanLabel("bond_guess_vdw_factor")).toBe("Bond guess vdW factor");
    expect(humanLabel("exact_match_min_identity_p")).toBe("Exact match min identity (0–1)");
  });
});

describe("config: parseConfigOptions", () => {
  it("reads config and presets", () => {
    const out = parseConfigOptions({ config: SAMPLE, presets: [QUICK, { bogus: 1 }] });
    expect(out?.config.verification.tm_score_threshold).toBe(0.5);
    expect(out?.presets.map((p) => p.id)).toEqual(["quick"]);
  });

  it("returns null for unusable input", () => {
    expect(parseConfigOptions(null)).toBeNull();
    expect(parseConfigOptions({ config: {} })).toBeNull();
    expect(parseConfigOptions(SAMPLE)).toBeNull();
  });
});

describe("config: presets and diffs", () => {
  it("applyPreset overrides without mutating the base", () => {
    const before = JSON.stringify(SAMPLE);
    const out = applyPreset(SAMPLE, QUICK);
    expect(out.identifiers.blast_nt).toBe(false);
    expect(out.identifiers.name_ccd).toBe(true);
    expect(JSON.stringify(SAMPLE)).toBe(before);
  });

  it("configDiff keeps only changed fields", () => {
    expect(configDiff(SAMPLE, SAMPLE)).toEqual({});
    expect(configDiff(applyPreset(SAMPLE, QUICK), SAMPLE)).toEqual(QUICK.overrides);
  });

  it("activePresetId recognises presets and custom configs", () => {
    const presets = [BALANCED, QUICK];
    expect(activePresetId(SAMPLE, SAMPLE, presets)).toBe("balanced");
    const quick = applyPreset(SAMPLE, QUICK);
    expect(activePresetId(quick, SAMPLE, presets)).toBe("quick");
    quick.verification.verify_top_n = 31;
    expect(activePresetId(quick, SAMPLE, presets)).toBeNull();
  });

  it("resolveConfigToPost posts only the diff, or nothing", () => {
    expect(resolveConfigToPost(SAMPLE, SAMPLE)).toBeNull();
    expect(resolveConfigToPost(null, SAMPLE)).toBeNull();
    const json = resolveConfigToPost(applyPreset(SAMPLE, QUICK), SAMPLE);
    expect(JSON.parse(json!)).toEqual(QUICK.overrides);
  });
});

describe("config: identifierGroups", () => {
  it("pairs exact/similar toggles and groups them", () => {
    const groups = Object.fromEntries(identifierGroups(SAMPLE.identifiers));
    expect(groups.Sequence).toEqual([{ name: "blast_nt", exact: true, similar: true }]);
    expect(groups.Names).toEqual([{ name: "name_ccd", exact: true }]);
    expect(groups.Other).toEqual([{ name: "foo", exact: true }]);
  });
});

describe("config: buildRunFormData", () => {
  it("appends files, optional run_name and config_json", () => {
    const f1 = new File(["x"], "system.pdb");
    const f2 = new File(["y"], "conf.ini");
    const form = buildRunFormData([f1, f2], "My Run", '{"a":1}', "quick");
    expect(form.getAll("files")).toHaveLength(2);
    expect(form.get("run_name")).toBe("My Run");
    expect(form.get("config_json")).toBe('{"a":1}');
    expect(form.get("preset")).toBe("quick");
  });

  it("omits run_name/config_json when not provided", () => {
    const form = buildRunFormData([new File(["x"], "a.pdb")], "", null);
    expect(form.get("run_name")).toBeNull();
    expect(form.get("config_json")).toBeNull();
  });
});

describe("status: statusStyle", () => {
  it("maps statuses to badge variants", () => {
    expect(statusStyle("success").variant).toBe("default");
    expect(statusStyle("failed").variant).toBe("error");
    expect(statusStyle("running").variant).toBe("outline");
    expect(statusStyle("pending").variant).toBe("outline");
    expect(statusStyle("warning").variant).toBe("outline");
    expect(statusStyle("mystery").label).toBe("Unknown");
  });
});

describe("status: runTitle", () => {
  it("prefers run_name, then input_kind, then short id", () => {
    expect(runTitle({ run_id: "abcd1234", run_name: "POPC", input_kind: "gromacs" })).toBe("POPC");
    expect(runTitle({ run_id: "abcd1234", run_name: null, input_kind: "gromacs" })).toBe("Gromacs");
    expect(runTitle({ run_id: "abcd1234", run_name: null, input_kind: null })).toBe("abcd1234…");
  });
});

describe("status: formatCreated", () => {
  it("formats a valid ISO timestamp and guards bad input", () => {
    expect(formatCreated("2026-10-01T09:00:00Z")).not.toBe("—");
    expect(formatCreated("not-a-date")).toBe("—");
    expect(formatCreated(null)).toBe("—");
  });
});

describe("status: queueChipText", () => {
  it("derives queue position text", () => {
    expect(queueChipText(null)).toBe("in queue");
    expect(queueChipText({ state: "queued", position: 3 })).toBe("in queue · #3");
    expect(queueChipText({ state: "queued", ahead: 2 })).toBe("in queue · 2 ahead");
    expect(queueChipText({ state: "running" })).toBe("starting…");
  });
});

describe("config: v3.142 Phase 3 weights helper", () => {
  it("normalizedWeights mirrors backend sum-normalization", () => {
    expect(normalizedWeights({ resolver_weight: 0.4, similarity_weight: 0.4, annotation_weight: 0.2 }))
      .toEqual([0.4, 0.4, 0.2]);
    expect(normalizedWeights({ resolver_weight: 0.5, similarity_weight: 0.5, annotation_weight: 0.5 }))
      .toEqual([1 / 3, 1 / 3, 1 / 3]);
  });
  it("normalizedWeights falls back to equal thirds on zero/negative sums", () => {
    expect(normalizedWeights({ resolver_weight: 0, similarity_weight: 0, annotation_weight: 0 }))
      .toEqual([1 / 3, 1 / 3, 1 / 3]);
    expect(normalizedWeights({ resolver_weight: -1, similarity_weight: 0.1, annotation_weight: 0.1 }))
      .toEqual([0, 0.5, 0.5]);
  });
  it("normalizedWeights returns null on non-finite input", () => {
    expect(normalizedWeights({ resolver_weight: NaN, similarity_weight: 0.4, annotation_weight: 0.2 })).toBeNull();
  });
  it("FIELD_HELP documents the three confidence weights", () => {
    for (const k of ["verification.resolver_weight", "verification.similarity_weight", "verification.annotation_weight"]) {
      expect(FIELD_HELP[k], k).toBeTruthy();
    }
  });
});
