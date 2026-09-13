"""Network transport preferences.

PUG-REST's IPv6 endpoint blackholes our cluster traffic (2026-09-12:
every request 503 ServerBusy via 2600:1901:... while IPv4 34.107.134.59
returns 200 for the same URL). Prefer IPv4 for host resolution in
processes that call NCBI/PUG endpoints.
"""

from __future__ import annotations

import socket

_installed = False
_orig_getaddrinfo = socket.getaddrinfo


def prefer_ipv4() -> None:
    """Make socket.getaddrinfo yield IPv4 addresses first (process-wide)."""
    global _installed
    if _installed:
        return

    def _ipv4_first(host, port, family=0, type=0, proto=0, flags=0):
        results = _orig_getaddrinfo(host, port, family, type, proto, flags)
        v4 = [r for r in results if r[0] == socket.AF_INET]
        return v4 if v4 else results

    socket.getaddrinfo = _ipv4_first
    _installed = True
