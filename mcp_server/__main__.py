"""Run the BioID MCP server: ``python -m mcp_server``."""
from __future__ import annotations

import logging
import os

import uvicorn

from .config import Settings
from .server import build_server


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings.from_env()
    logging.getLogger("bioid_mcp").info(
        "BioID MCP server on %s:%s/mcp -> API %s", settings.host, settings.port, settings.api_url)
    app = build_server(settings).streamable_http_app()
    # proxy_headers off: the client address forwarded to the API is built
    # from X-Forwarded-For + the peer explicitly (server._client_ip).
    uvicorn.run(app, host=settings.host, port=settings.port, proxy_headers=False,
                log_level=os.environ.get("LOG_LEVEL", "info").lower(), timeout_graceful_shutdown=10)


if __name__ == "__main__":
    main()
