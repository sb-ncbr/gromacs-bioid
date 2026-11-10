"""The ASGI app: /healthz, and a JSON-RPC tool call over Streamable HTTP
(stateless, JSON responses) that forwards the caller's address."""
from __future__ import annotations

import json

import httpx
import pytest

pytestmark = pytest.mark.anyio

HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@pytest.fixture
async def http(server):
    app = server.streamable_http_app()
    async with server.session_manager.run():
        transport = httpx.ASGITransport(app=app, client=("203.0.113.9", 4000))
        async with httpx.AsyncClient(transport=transport, base_url="http://mcp.test") as c:
            yield c


async def test_healthz(http):
    resp = await http.get("/healthz")
    assert resp.status_code == 200 and resp.json()["status"] == "ok"


async def test_initialize_and_list_tools(http):
    init = await http.post("/mcp", headers=HEADERS, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "test", "version": "0"}}})
    assert init.status_code == 200
    assert init.headers["content-type"].startswith("application/json")
    result = init.json()["result"]
    assert result["serverInfo"]["name"] == "BioID"
    assert "submit" in result["instructions"]
    tools = await http.post("/mcp", headers=HEADERS,
                            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert len(tools.json()["result"]["tools"]) == 10


async def test_submit_forwards_client_address(http, api):
    route = api.post("https://api.test/api/v1/runs").respond(json={"run_id": "r1", "status": "queued",
                                                   "message": "", "results_url": ""})
    resp = await http.post("/mcp", headers={**HEADERS, "X-Forwarded-For": "198.51.100.7"}, json={
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "submit_files",
                   "arguments": {"files": [{"name": "a.pdb", "text": "ATOM"}]}}})
    body = resp.json()["result"]
    assert body["isError"] is False, body
    assert json.loads(body["content"][0]["text"])["run_id"] == "r1"
    assert route.calls.last.request.headers["x-forwarded-for"] == "198.51.100.7, 203.0.113.9"
    assert route.calls.last.request.headers["user-agent"].startswith("bioid-mcp/")


async def test_request_body_limit(http):
    # settings fixture caps uploads at 1000 bytes -> body limit ~1 MiB + 1333 B
    big = "x" * (2 * 1024 * 1024)
    resp = await http.post("/mcp", headers=HEADERS, json={
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "submit_files", "arguments": {"files": [{"name": "a.pdb", "text": big}]}}})
    assert resp.status_code == 413
