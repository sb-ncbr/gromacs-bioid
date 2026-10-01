import { describe, expect, it } from "vitest";
import {
  ACCEPTED_EXTENSIONS,
  ACCEPT_MAP,
  fileExtension,
  truncateFileName,
} from "./fileTypes";
import {
  applyFastMode,
  buildRunFormData,
  humanLabel,
  parseConfigPayload,
  resolveConfigToPost,
  shouldRequireNonNegative,
  validateNumberInput,
  type RunConfig,
} from "./config";
import {
  formatCreated,
  queueChipText,
  runTitle,
  statusStyle,
} from "./status";

const SAMPLE: RunConfig = {
  executor: { signatures_parallel: false, identifiers_parallel: false, verification_parallel: false },
  verification: { tm_score_threshold: 0.5, min_final_confidence: 0.0 },
};

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

  it("ACCEPT_MAP covers the legacy extensions", () => {
    for (const ext of ["tpr", "gro", "top", "itp", "pdb", "json", "yaml", "yml", "zip", "tar", "ini"]) {
      expect(ACCEPTED_EXTENSIONS).toContain(ext);
    }
    expect(ACCEPT_MAP["application/octet-stream"]).toEqual([
      ".tpr", ".gro", ".top", ".itp", ".pdb",
    ]);
  });
});

describe("config: non-negative rules", () => {
  it("bounds fields whose names imply a floor", () => {
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

describe("config: applyFastMode", () => {
  it("sets the three parallel flags without mutating the input", () => {
    const before = JSON.stringify(SAMPLE);
    const out = applyFastMode(SAMPLE, true);
    expect(out.executor.signatures_parallel).toBe(true);
    expect(out.executor.identifiers_parallel).toBe(true);
    expect(out.executor.verification_parallel).toBe(true);
    expect(JSON.stringify(SAMPLE)).toBe(before);
  });
});

describe("config: humanLabel", () => {
  it("title-cases snake_case keys", () => {
    expect(humanLabel("signatures_parallel")).toBe("Signatures Parallel");
    expect(humanLabel("global_timeout_s")).toBe("Global Timeout S");
  });
});

describe("config: parseConfigPayload", () => {
  it("accepts a direct section dict", () => {
    const out = parseConfigPayload(SAMPLE);
    expect(out?.executor.signatures_parallel).toBe(false);
    expect(out?.verification.tm_score_threshold).toBe(0.5);
  });

  it("accepts the { error, config } error shape", () => {
    const out = parseConfigPayload({ error: "boom", config: SAMPLE });
    expect(out?.verification.min_final_confidence).toBe(0.0);
  });

  it("returns null for empty/non-object input", () => {
    expect(parseConfigPayload(null)).toBeNull();
    expect(parseConfigPayload("nope")).toBeNull();
    expect(parseConfigPayload({ a: 1 })).toBeNull();
  });
});

describe("config: resolveConfigToPost", () => {
  it("posts nothing unless customized or fast", () => {
    expect(resolveConfigToPost(SAMPLE, { customized: false, fastMode: false })).toBeNull();
  });

  it("applies fast-mode flags when enabled", () => {
    const json = resolveConfigToPost(SAMPLE, { customized: false, fastMode: true });
    expect(json).not.toBeNull();
    const parsed = JSON.parse(json!);
    expect(parsed.executor.signatures_parallel).toBe(true);
  });

  it("serializes the edited config when customized", () => {
    const json = resolveConfigToPost(SAMPLE, { customized: true, fastMode: false });
    const parsed = JSON.parse(json!);
    expect(parsed.verification.tm_score_threshold).toBe(0.5);
    expect(parsed.executor.signatures_parallel).toBe(false);
  });
});

describe("config: buildRunFormData", () => {
  it("appends files, optional run_name and config_json", () => {
    const f1 = new File(["x"], "system.pdb");
    const f2 = new File(["y"], "conf.ini");
    const form = buildRunFormData([f1, f2], "My Run", '{"a":1}');
    expect(form.getAll("files")).toHaveLength(2);
    expect(form.get("run_name")).toBe("My Run");
    expect(form.get("config_json")).toBe('{"a":1}');
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
    expect(statusStyle("running").variant).toBe("secondary");
    expect(statusStyle("pending").variant).toBe("outline");
    expect(statusStyle("warning").variant).toBe("secondary");
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
