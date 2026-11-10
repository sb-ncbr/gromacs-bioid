import { afterEach, describe, expect, it, vi } from "vitest";
import { sendPageview } from "./pageviews";

describe("pageview beacon", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("posts the path and the client, never for the admin page", () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    sendPageview("/runs/abc", "https://x.org/");
    sendPageview("/admin", null);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/events/pageview");
    expect(JSON.parse(init.body)).toEqual({ path: "/runs/abc", referrer: "https://x.org/" });
    expect(init.headers["X-BioID-Client"]).toBe("web");
  });

  it("respects Do Not Track", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    // jsdom has no navigator.doNotTrack: define it for this test
    Object.defineProperty(navigator, "doNotTrack", { value: "1", configurable: true });
    try {
      sendPageview("/", null);
      expect(fetchMock).not.toHaveBeenCalled();
    } finally {
      Object.defineProperty(navigator, "doNotTrack", { value: undefined, configurable: true });
    }
  });
});
