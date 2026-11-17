import { describe, expect, it } from "vitest";
import { retentionView } from "./retentionModel";

const NOW = Date.parse("2026-11-17T12:00:00Z");

describe("retentionView", () => {
  it("shows the expiry and only the choices that extend it", () => {
    const v = retentionView(
      { policy: "default", days: 30, expires_at: "2026-12-17T12:00:00Z", owner_choices: [30, 90, 180, 365] },
      NOW,
    );
    expect(v?.text).toBe("Kept until 17 Dec 2026 (in 30 days), then deleted. Download results.json to keep a copy.");
    expect(v?.soon).toBe(false);
    expect(v?.choices).toEqual([90, 180, 365]);
  });

  it("emphasises a run deleted within a week", () => {
    const v = retentionView({ policy: "days", days: 1, expires_at: "2026-11-18T12:00:00Z" }, NOW);
    expect(v?.text).toContain("(tomorrow)");
    expect(v?.soon).toBe(true);
    expect(v?.choices).toEqual([]);
  });

  it("examples and preserved runs are kept; unfinished runs show nothing", () => {
    expect(retentionView({ policy: "preserve", example: true }, NOW)?.text).toContain("example run");
    expect(retentionView({ policy: "preserve", expires_at: null }, NOW)?.text).toContain("permanently");
    expect(retentionView({ policy: "default", expires_at: null }, NOW)).toBeNull();
    expect(retentionView(null, NOW)).toBeNull();
  });
});
