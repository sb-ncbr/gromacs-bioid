/**
 * Page-view beacon for the admin page's traffic statistics
 * (POST /api/v1/events/pageview). One call per route change; never for the
 * admin page; never when the browser asks not to be tracked. The server
 * stores no address, only a keyed hash and the approximate location.
 */
import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

function trackingAllowed(): boolean {
  const nav = navigator as Navigator & { globalPrivacyControl?: boolean };
  return nav.doNotTrack !== "1" && nav.globalPrivacyControl !== true;
}

export function sendPageview(path: string, referrer: string | null) {
  if (path.startsWith("/admin") || !trackingAllowed()) return;
  void fetch("/api/v1/events/pageview", {
    method: "POST",
    keepalive: true,
    headers: { "Content-Type": "application/json", "X-BioID-Client": "web" },
    body: JSON.stringify({ path, referrer }),
  }).catch(() => {
    // statistics are best-effort
  });
}

/** Sends a page view on every route change (the referrer only with the first). */
export function usePageviews() {
  const { pathname } = useLocation();
  const first = useRef(true);
  useEffect(() => {
    sendPageview(pathname, first.current ? document.referrer || null : null);
    first.current = false;
  }, [pathname]);
}
