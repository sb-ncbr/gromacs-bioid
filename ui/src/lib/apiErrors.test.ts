import { describe, expect, it, beforeEach, vi } from "vitest";
import { ApiError, apiErrorMessage } from "./api/client";
import { forgetOwnerToken, ownerHeaders, ownerToken, rememberOwnerToken } from "./ownerTokens";

describe("apiErrorMessage", () => {
  it("shows the API's detail (limits, rejected files, owner token)", () => {
    const err = new ApiError(429, JSON.stringify({ detail: "Too many runs from your network address." }), 900);
    expect(apiErrorMessage(err, "fallback")).toBe("Too many runs from your network address.");
  });

  it("explains a 429 / 413 without a JSON body", () => {
    expect(apiErrorMessage(new ApiError(429, "<html>", 600), "x")).toBe(
      "BioID is busy. Please try again in about 10 minutes.",
    );
    expect(apiErrorMessage(new ApiError(413, "<html>"), "x")).toMatch(/128 MiB/);
  });

  it("falls back for network errors and bodies without detail", () => {
    expect(apiErrorMessage(new TypeError("Failed to fetch"), "fallback")).toBe("fallback");
    expect(apiErrorMessage(new ApiError(500, "{}"), "fallback")).toBe("fallback");
  });
});

describe("owner tokens", () => {
  beforeEach(() => {
    // Node's own (disabled) localStorage shadows jsdom's here: use a memory one.
    const store = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
      clear: () => store.clear(),
    });
  });

  it("remembers and forgets a run's token", () => {
    expect(ownerHeaders("r1")).toBeUndefined();
    rememberOwnerToken("r1", "tok");
    rememberOwnerToken("r2", null);
    expect(ownerToken("r1")).toBe("tok");
    expect(ownerHeaders("r1")).toEqual({ "X-Owner-Token": "tok" });
    expect(ownerToken("r2")).toBeNull();
    forgetOwnerToken("r1");
    expect(ownerToken("r1")).toBeNull();
  });
});
