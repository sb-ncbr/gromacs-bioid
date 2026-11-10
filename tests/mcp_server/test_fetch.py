"""SSRF guards and size caps of the URL / RCSB downloader."""
from __future__ import annotations

import socket

import httpx
import pytest
import respx

import mcp_server.fetch as fetch
from mcp_server.client import BioIDError

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "10.0.0.1", "10.43.193.47", "172.16.5.4", "192.168.1.1", "169.254.169.254",
    "100.64.0.1", "0.0.0.0", "224.0.0.1", "::1", "fe80::1", "fd00::1", "::ffff:10.0.0.1",
])
async def test_resolve_public_rejects_literals(ip):
    with pytest.raises(BioIDError, match="non-public"):
        await fetch.resolve_public(ip)


async def test_resolve_public_accepts_global_literal():
    assert await fetch.resolve_public("93.184.216.34") == "93.184.216.34"


async def test_resolve_public_rejects_mixed_dns(monkeypatch):
    """A host is refused if ANY of its addresses is private."""
    async def fake_getaddrinfo(self, host, port, **kw):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443))]
    import asyncio
    monkeypatch.setattr(type(asyncio.get_running_loop()), "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(BioIDError, match="non-public"):
        await fetch.resolve_public("evil.example")


async def test_resolve_unknown_host(monkeypatch):
    async def fake_getaddrinfo(self, host, port, **kw):
        raise socket.gaierror("nope")
    import asyncio
    monkeypatch.setattr(type(asyncio.get_running_loop()), "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(BioIDError, match="Could not resolve"):
        await fetch.resolve_public("nx.example")


@pytest.fixture
def public_dns(monkeypatch):
    table = {"files.example": "93.184.216.34", "cdn.example": "93.184.216.35",
             "internal.example": None}

    async def resolve(host):
        ip = table.get(host)
        if ip is None:
            raise BioIDError(f"Refusing to download from '{host}': it resolves to a non-public address.")
        return ip
    monkeypatch.setattr(fetch, "resolve_public", resolve)


async def test_redirect_is_rechecked(public_dns):
    with respx.mock:
        respx.get("https://93.184.216.34/a.pdb").respond(
            302, headers={"location": "https://internal.example/secret"})
        with pytest.raises(BioIDError, match="non-public"):
            await fetch.fetch_url("https://files.example/a.pdb", cap=100, timeout=5)


async def test_redirect_followed_to_public_host(public_dns):
    with respx.mock:
        respx.get("https://93.184.216.34/a").respond(302, headers={"location": "https://cdn.example/b/x.cif"})
        final = respx.get("https://93.184.216.35/b/x.cif").respond(content=b"data_x")
        name, body = await fetch.fetch_url("https://files.example/a", cap=100, timeout=5)
    assert (name, body) == ("x.cif", b"data_x")
    assert final.calls.last.request.headers["host"] == "cdn.example"


async def test_redirect_to_http_refused(public_dns):
    with respx.mock:
        respx.get("https://93.184.216.34/a").respond(301, headers={"location": "http://cdn.example/x"})
        with pytest.raises(BioIDError, match="Only https"):
            await fetch.fetch_url("https://files.example/a", cap=100, timeout=5)


async def test_too_many_redirects(public_dns):
    with respx.mock:
        respx.get("https://93.184.216.34/loop").respond(302, headers={"location": "/loop"})
        with pytest.raises(BioIDError, match="Too many redirects"):
            await fetch.fetch_url("https://files.example/loop", cap=100, timeout=5)


async def test_size_cap_by_header_and_stream(public_dns):
    with respx.mock:
        respx.get("https://93.184.216.34/big").respond(content=b"x" * 500)
        with pytest.raises(BioIDError, match="limit"):
            await fetch.fetch_url("https://files.example/big", cap=100, timeout=5)


async def test_content_disposition_name(public_dns):
    with respx.mock:
        respx.get("https://93.184.216.34/dl").respond(
            content=b"PK", headers={"content-disposition": 'attachment; filename="../../sys.zip"'})
        name, _ = await fetch.fetch_url("https://files.example/dl", cap=100, timeout=5)
    assert name == "sys.zip"


async def test_http_error_status(public_dns):
    with respx.mock:
        respx.get("https://93.184.216.34/gone").respond(410)
        with pytest.raises(BioIDError, match="HTTP 410"):
            await fetch.fetch_url("https://files.example/gone", cap=100, timeout=5)


async def test_pdb_entry_size_cap():
    with respx.mock:
        respx.get("https://files.rcsb.org/download/1ABC.pdb").respond(content=b"x" * 500)
        with pytest.raises(BioIDError, match="limit"):
            await fetch.fetch_pdb_entry("1abc", cap=100, timeout=5)


async def test_pdb_entry_timeout():
    with respx.mock:
        respx.get("https://files.rcsb.org/download/1ABC.pdb").mock(side_effect=httpx.ConnectTimeout("t"))
        with pytest.raises(BioIDError, match="timed out"):
            await fetch.fetch_pdb_entry("1ABC", cap=100, timeout=5)


@pytest.mark.parametrize("pid, norm", [("3ptb", "3PTB"), ("PDB_00003PTB", "pdb_00003ptb")])
def test_pdb_id_normalisation(pid, norm):
    assert fetch.normalise_pdb_id(pid) == norm


@pytest.mark.parametrize("name, ok", [
    ("a.pdb", True), ("A.PDB", True), ("x.tar.gz", True), ("t.tpr", True), ("s.data", True),
    ("a.txt", False), ("a.pdb.gz", False), ("a", False),
])
def test_accepted_name(name, ok):
    assert fetch.accepted_name(name) is ok
