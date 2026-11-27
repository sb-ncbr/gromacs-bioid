"""GitHub #24: the requester identity comes from trusted proxy hops only."""
from types import SimpleNamespace

from src_new.api.routes.runs import _requester_ip


def _req(peer, xff=None):
    headers = {"x-forwarded-for": xff} if xff else {}
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


def test_ingress_peer_header_names_the_client():
    assert _requester_ip(_req("10.42.7.1", "198.51.100.9")) == "198.51.100.9"


def test_spoofed_leftmost_hop_is_ignored():
    # client sends 'X-Forwarded-For: 1.2.3.4'; the ingress appends the real one
    assert _requester_ip(_req("10.42.7.1", "1.2.3.4, 198.51.100.9")) == "198.51.100.9"


def test_untrusted_direct_peer_ignores_the_header():
    assert _requester_ip(_req("198.51.100.9", "1.2.3.4")) == "198.51.100.9"


def test_mcp_hop_chain():
    # MCP pod forwards "<client>, <ingress pod>" and connects from its own pod IP
    assert _requester_ip(_req("10.42.3.3", "198.51.100.9, 10.42.7.1")) == "198.51.100.9"


def test_in_cluster_client_without_header():
    assert _requester_ip(_req("10.42.3.3")) == "10.42.3.3"


def test_trusted_ranges_configurable(monkeypatch):
    monkeypatch.setenv("BAT3_TRUSTED_PROXIES", "192.0.2.0/24")
    assert _requester_ip(_req("192.0.2.5", "198.51.100.9")) == "198.51.100.9"
    assert _requester_ip(_req("10.42.7.1", "198.51.100.9")) == "10.42.7.1"
