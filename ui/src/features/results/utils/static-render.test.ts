import { describe, expect, it } from "vitest";
import {
  isOverInteractivityGate,
  resolveStaticPngPath,
  STATIC_PNG_LEGACY_PATH,
} from "./static-render";

describe("isOverInteractivityGate", () => {
  it("is false below the limit", () => {
    expect(isOverInteractivityGate(999_999)).toBe(false);
  });

  it("is true exactly at the limit (1 000 000 atoms)", () => {
    expect(isOverInteractivityGate(1_000_000)).toBe(true);
  });

  it("is false when the API has no atom count (older runs)", () => {
    expect(isOverInteractivityGate(null)).toBe(false);
    expect(isOverInteractivityGate(undefined)).toBe(false);
  });
});

describe("resolveStaticPngPath", () => {
  it("prefers the per-segment PNG for segment views", () => {
    const paths = {
      system_png: "render/system.png",
      segment_pngs: { seg_1_A: "render/segments/seg_1_A.png" },
    };
    expect(resolveStaticPngPath(paths as never, "seg_1_A")).toBe("render/segments/seg_1_A.png");
  });

  it("falls back to the system PNG for segments without their own", () => {
    const paths = {
      system_png: "render/system.png",
      segment_pngs: { seg_1_A: "render/segments/seg_1_A.png" },
    };
    expect(resolveStaticPngPath(paths as never, "seg_2_B")).toBe("render/system.png");
  });

  it("never uses a segment PNG for SYSTEM views", () => {
    const paths = {
      system_png: "render/system.png",
      segment_pngs: { seg_1_A: "render/segments/seg_1_A.png" },
    };
    expect(resolveStaticPngPath(paths as never, "SYSTEM")).toBe("render/system.png");
  });

  it("uses the legacy hard-coded path for pre-v3.137 responses", () => {
    expect(resolveStaticPngPath(undefined, "SYSTEM")).toBe(STATIC_PNG_LEGACY_PATH);
    expect(resolveStaticPngPath({} as never, "seg_x")).toBe(STATIC_PNG_LEGACY_PATH);
  });
});
