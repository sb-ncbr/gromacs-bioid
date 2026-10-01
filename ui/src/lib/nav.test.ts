import { describe, expect, it } from "vitest";
import { buildRunUrl, parseRunQuery } from "./nav";

describe("run query deep-linking", () => {
  it("parses defaults when params absent", () => {
    expect(parseRunQuery("")).toEqual({ segment: "SYSTEM", tab: "overview" });
  });

  it("parses explicit segment and tab", () => {
    expect(parseRunQuery("?segment=A&tab=signatures")).toEqual({
      segment: "A",
      tab: "signatures",
    });
  });

  it("rejects unknown tab, keeps segment", () => {
    expect(parseRunQuery("?segment=B&tab=bogus")).toEqual({ segment: "B", tab: "overview" });
  });

  it("round-trips build<->parse", () => {
    const url = buildRunUrl("abc-123", { segment: "C", tab: "warnings" });
    expect(url).toBe("/runs/abc-123?segment=C&tab=warnings");
    const parsed = parseRunQuery(url.slice("/runs/abc-123".length));
    expect(parsed).toEqual({ segment: "C", tab: "warnings" });
  });

  it("omits default values from built url", () => {
    expect(buildRunUrl("r1", { segment: "SYSTEM", tab: "overview" })).toBe("/runs/r1");
  });
});
