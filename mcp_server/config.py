"""Runtime settings, read once from the environment."""
from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_URL = "https://bioid-ceitec.dyn.cloud.e-infra.cz"


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    #: BioID REST API base (no trailing slash, no /api/v1). In-cluster this is
    #: the API service, e.g. http://bat3-ceitec-bat3-api:8000.
    api_url: str = DEFAULT_URL
    #: Public BioID URL used for links in tool output.
    public_url: str = DEFAULT_URL
    #: Timeout for read calls to the API (seconds).
    api_timeout_s: float = 30.0
    #: Timeout for the upload that creates a run (seconds).
    submit_timeout_s: float = 180.0
    #: Cap on the total size of the files of one submission (bytes).
    max_upload_bytes: int = 50 * 1024 * 1024
    #: Timeout for downloading an input from RCSB or a URL (seconds).
    fetch_timeout_s: float = 60.0
    host: str = "0.0.0.0"
    port: int = 8080

    @classmethod
    def from_env(cls) -> "Settings":
        api = os.environ.get("BIOID_API_URL", DEFAULT_URL).rstrip("/")
        public = os.environ.get("BIOID_PUBLIC_URL", DEFAULT_URL).rstrip("/")
        return cls(
            api_url=api,
            public_url=public,
            api_timeout_s=_float("BIOID_API_TIMEOUT_S", 30.0),
            submit_timeout_s=_float("BIOID_SUBMIT_TIMEOUT_S", 180.0),
            max_upload_bytes=int(_float("BIOID_MCP_MAX_UPLOAD_MB", 50.0) * 1024 * 1024),
            fetch_timeout_s=_float("BIOID_FETCH_TIMEOUT_S", 60.0),
            host=os.environ.get("BIOID_MCP_HOST", "0.0.0.0"),
            port=int(_float("PORT", 8080)),
        )

    def results_page(self, run_id: str) -> str:
        return f"{self.public_url}/runs/{run_id}"

    def results_csv(self, run_id: str) -> str:
        return f"{self.public_url}/api/v1/runs/{run_id}/download/results.csv"
