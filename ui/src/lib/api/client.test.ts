import { afterEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "./admin";
import { api, apiErrorMessage, ApiError } from "./client";

const ingressPage = () =>
  new Response("<html><head><title>503 Service not available</title></head></html>", {
    status: 200,
    headers: { "content-type": "text/html" },
  });

afterEach(() => vi.unstubAllGlobals());

describe("an ingress error page is not data (2026-11-17 outage)", () => {
  it("the public client throws 503 with a readable message", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ingressPage()));
    const err = await api.get("/api/v1/runs/x/status").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(503);
    expect(apiErrorMessage(err, "fallback")).toContain("not available right now");
  });

  it("the admin client throws instead of handing the page to the dashboard", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ingressPage()));
    await expect(adminApi.overview("token")).rejects.toBeInstanceOf(ApiError);
  });
});
