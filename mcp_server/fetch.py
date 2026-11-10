"""Downloading inputs for a submission: RCSB PDB entries and public URLs.

URL downloads are server-side requests made on behalf of whoever calls the
tool, from inside the cluster, so they are locked down against SSRF:

* https only, default port only, no credentials in the URL;
* the host name is resolved here and EVERY address must be globally
  routable (no private, loopback, link-local, CGNAT, multicast or reserved
  ranges, which covers the cluster's pod/service networks and cloud
  metadata endpoints);
* the connection goes to the address that was checked (pinned), with the
  original host name kept for SNI, certificate verification and the Host
  header, so a second DNS answer cannot redirect it (DNS rebinding);
* redirects are followed by hand, at most 5, each hop checked the same way;
* the body is streamed and abandoned once it passes the size cap.
"""
from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from email.message import Message
from typing import Optional
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import httpx

from .client import USER_AGENT, BioIDError

RCSB_DOWNLOAD = "https://files.rcsb.org/download"

# 4-character PDB ids, and the extended pdb_0000xxxx form.
_PDB_ID_RE = re.compile(r"^(?:[0-9][A-Za-z0-9]{3}|pdb_[0-9]{4}[0-9A-Za-z]{4})$", re.IGNORECASE)

# Extensions BioID reads (ui/src/features/frontpage/fileTypes.ts), longest first.
ACCEPTED_SUFFIXES = (
    ".tar.gz", ".tgz", ".tpr", ".gro", ".top", ".itp", ".trr", ".xtc",
    ".prmtop", ".parm7", ".nc", ".rst7", ".inpcrd", ".restrt", ".mdcrd",
    ".psf", ".pdb", ".crd", ".dcd", ".data", ".cif", ".zip", ".tar",
)

MAX_REDIRECTS = 5


def accepted_name(name: str) -> bool:
    return name.lower().endswith(ACCEPTED_SUFFIXES)


def normalise_pdb_id(pdb_id: str) -> str:
    pdb_id = (pdb_id or "").strip()
    if not _PDB_ID_RE.match(pdb_id):
        raise BioIDError(
            f"'{pdb_id}' is not a PDB id (expected 4 characters such as '3PTB', "
            "or the extended form 'pdb_00003ptb').")
    return pdb_id.upper() if len(pdb_id) == 4 else pdb_id.lower()


async def _read_capped(resp: httpx.Response, cap: int, what: str) -> bytes:
    length = resp.headers.get("content-length")
    if length and length.isdigit() and int(length) > cap:
        raise BioIDError(f"{what} is {int(length) / 1e6:.1f} MB; the limit is {cap / 1e6:.0f} MB.")
    chunks: list[bytes] = []
    total = 0
    async for chunk in resp.aiter_bytes():
        total += len(chunk)
        if total > cap:
            raise BioIDError(f"{what} is larger than the {cap / 1e6:.0f} MB limit.")
        chunks.append(chunk)
    return b"".join(chunks)


async def fetch_pdb_entry(pdb_id: str, *, cap: int, timeout: float,
                          transport: Optional[httpx.AsyncBaseTransport] = None) -> tuple[str, bytes]:
    """Download an entry from RCSB: legacy PDB format when the entry has one,
    otherwise mmCIF (large structures exist only as mmCIF)."""
    pdb_id = normalise_pdb_id(pdb_id)
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": USER_AGENT},
                                 transport=transport, follow_redirects=True) as http:
        for ext in ("pdb", "cif"):
            url = f"{RCSB_DOWNLOAD}/{pdb_id}.{ext}"
            try:
                async with http.stream("GET", url) as resp:
                    if resp.status_code == 404:
                        continue
                    if resp.status_code >= 400:
                        raise BioIDError(f"RCSB answered HTTP {resp.status_code} for {url}.")
                    body = await _read_capped(resp, cap, f"PDB entry {pdb_id}")
            except httpx.TimeoutException as e:
                raise BioIDError(f"Downloading {pdb_id} from RCSB timed out.") from e
            except httpx.HTTPError as e:
                raise BioIDError(f"Could not download {pdb_id} from RCSB ({type(e).__name__}).") from e
            if body:
                return f"{pdb_id}.{ext}", body
    raise BioIDError(f"PDB entry {pdb_id} was not found at RCSB (no .pdb or .cif file).")


# -- arbitrary URLs ------------------------------------------------------

def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


async def resolve_public(host: str) -> str:
    """Resolve ``host`` and return one address, refusing the whole host if
    any of its addresses is not public."""
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        addrs = [literal]
    else:
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except (socket.gaierror, UnicodeError) as e:
            raise BioIDError(f"Could not resolve the host '{host}'.") from e
        addrs = []
        for info in infos:
            addr = ipaddress.ip_address(info[4][0].split("%", 1)[0])
            if addr not in addrs:
                addrs.append(addr)
    if not addrs:
        raise BioIDError(f"Could not resolve the host '{host}'.")
    for addr in addrs:
        if not _is_public(addr):
            raise BioIDError(
                f"Refusing to download from '{host}': it resolves to a non-public address. "
                "Only publicly reachable https URLs can be fetched.")
    return str(addrs[0])


def _check_url(url: str):
    """Validate a URL; return its urlsplit() parts."""
    try:
        parts = urlsplit(url)
    except ValueError as e:
        raise BioIDError(f"'{url}' is not a valid URL.") from e
    if parts.scheme != "https":
        raise BioIDError("Only https:// URLs can be fetched.")
    if parts.username or parts.password:
        raise BioIDError("URLs with credentials are not accepted.")
    if not parts.hostname:
        raise BioIDError(f"'{url}' has no host.")
    try:
        port = parts.port
    except ValueError as e:
        raise BioIDError(f"'{url}' has an invalid port.") from e
    if port not in (None, 443):
        raise BioIDError("Only the default https port (443) is allowed.")
    return parts


def _filename(url: str, resp: httpx.Response) -> str:
    disposition = resp.headers.get("content-disposition")
    if disposition:
        msg = Message()
        msg["content-disposition"] = disposition
        name = msg.get_filename()
        if name:
            name = name.replace("\\", "/").rsplit("/", 1)[-1].strip()
            if name:
                return name
    path = unquote(urlsplit(url).path)
    return path.rstrip("/").rsplit("/", 1)[-1]


async def fetch_url(url: str, *, cap: int, timeout: float, filename: Optional[str] = None,
                    transport: Optional[httpx.AsyncBaseTransport] = None) -> tuple[str, bytes]:
    """Download a public https URL with the SSRF guards above."""
    current = url.strip()
    async with httpx.AsyncClient(timeout=timeout, transport=transport, trust_env=False,
                                 follow_redirects=False) as http:
        for _hop in range(MAX_REDIRECTS + 1):
            parts = _check_url(current)
            host = parts.hostname
            ip = await resolve_public(host)
            ip_host = f"[{ip}]" if ":" in ip else ip
            request = http.build_request(
                "GET", urlunsplit(("https", ip_host, parts.path or "/", parts.query, "")),
                headers={"Host": host, "User-Agent": USER_AGENT, "Accept": "*/*"},
                extensions={"sni_hostname": host},
            )
            try:
                resp = await http.send(request, stream=True)
            except httpx.TimeoutException as e:
                raise BioIDError(f"Downloading {current} timed out.") from e
            except httpx.HTTPError as e:
                raise BioIDError(f"Could not download {current} ({type(e).__name__}: {e}).") from e
            try:
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location")
                    if not location:
                        raise BioIDError(f"{current} redirected without a location.")
                    current = urljoin(current, location)
                    continue
                if resp.status_code >= 400:
                    raise BioIDError(f"Downloading {current} failed with HTTP {resp.status_code}.")
                body = await _read_capped(resp, cap, "The file")
                name = (filename or _filename(current, resp)).strip()
            except httpx.HTTPError as e:
                raise BioIDError(f"Downloading {current} failed ({type(e).__name__}).") from e
            finally:
                await resp.aclose()
            if not body:
                raise BioIDError(f"{current} returned an empty file.")
            return name, body
    raise BioIDError(f"Too many redirects (more than {MAX_REDIRECTS}) from {url}.")
