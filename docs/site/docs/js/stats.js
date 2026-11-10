// Page-view beacon for BioID's traffic statistics (admin page). Only on the
// BioID host (the API is same-origin there); skipped with Do Not Track. The
// server stores no address: a keyed hash and the approximate location only.
(function () {
  if (location.pathname.indexOf("/documentation/") !== 0) return;
  if (navigator.doNotTrack === "1" || navigator.globalPrivacyControl === true) return;
  function send() {
    fetch("/api/v1/events/pageview", {
      method: "POST",
      keepalive: true,
      headers: { "Content-Type": "application/json", "X-BioID-Client": "docs" },
      body: JSON.stringify({ path: location.pathname, referrer: document.referrer || null }),
    }).catch(function () {});
  }
  // mkdocs-material instant navigation re-runs document$ subscribers
  if (window.document$ && window.document$.subscribe) window.document$.subscribe(send);
  else send();
})();
