#!/usr/bin/env python
"""download_with_retry.py <url> <out> — retry-robust downloader for image layers.

Used instead of curl/wget (absent from python:*-slim) in Dockerfile.full.
Raises SystemExit(1) after 6 failed attempts; verifies a non-empty body.
"""

from __future__ import annotations

import os
import sys
import time

import requests


def main() -> int:
    url, out = sys.argv[1], sys.argv[2]
    err: Exception | None = None
    for attempt in range(6):
        try:
            r = requests.get(url, timeout=600, stream=True)
            r.raise_for_status()
            with open(out, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
            if os.path.getsize(out) == 0:
                raise IOError(f"empty download from {url}")
            return 0
        except Exception as e:  # noqa: BLE001 - build-layer robustness gate
            err = e
            time.sleep(3)
    print(f"download failed after 6 attempts: {url}: {err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
