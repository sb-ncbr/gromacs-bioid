"""Lipid shorthand identifier resolver using LIPID MAPS REST API."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING
from urllib.parse import quote

import requests

from ..base import IdentifierResolver, IdentifierResolutionError

if TYPE_CHECKING:
    from ...config.loader import RunConfig

logger = logging.getLogger("identifier")

#: Candidates kept per species (TG 52:2 lists 51 isomers; each is a remote
#: structure fetch in verification).
MAX_CANDIDATES = 25

_CHAIN = re.compile(r"^(O-|P-|d|t)?(\d+):(\d+)")


def species_shorthand(shorthand: str) -> str | None:
    """'PC(16:0/18:1(9Z))' -> 'PC 34:1'; 'PC(O-16:0/18:1)' -> 'PC O-34:1';
    'SM(d18:1/16:0)' -> 'SM 34:1;O2'; a species already ('ST 27:1;O') is
    kept; a bare class ('CL') or anything unparsable -> None."""
    text = (shorthand or "").strip()
    if "(" not in text:
        return text if re.search(r"\d+:\d+", text) and "/" not in text else None
    head, _, inner = text.partition("(")
    if not inner.endswith(")") or not head.strip():
        return None
    inner = inner[:-1]
    chains, depth, part = [], 0, ""
    for ch in inner:  # split on / or _ outside parentheses
        if ch in "/_" and depth == 0:
            chains.append(part)
            part = ""
            continue
        depth += (ch == "(") - (ch == ")")
        part += ch
    chains.append(part)
    carbons = bonds = 0
    prefix = oxygens = ""
    for chain in chains:
        m = _CHAIN.match(chain.strip())
        if not m:
            return None
        flag, c, d = m.groups()
        carbons, bonds = carbons + int(c), bonds + int(d)
        if flag in ("O-", "P-"):
            prefix = flag
        elif flag == "d":
            oxygens = ";O2"
        elif flag == "t":
            oxygens = ";O3"
    return f"{head.strip()} {prefix}{carbons}:{bonds}{oxygens}"


def _lm_ids(data) -> list[str]:
    """LM IDs from LMSD's answer: {"input","lm_id"} or {"Row1": {...}, ...} or []."""
    rows = [data] if isinstance(data, dict) and "lm_id" in data else (
        list(data.values()) if isinstance(data, dict) else data if isinstance(data, list) else [])
    return [str(r["lm_id"]) for r in rows if isinstance(r, dict) and r.get("lm_id")]


class LipidShorthandResolver(IdentifierResolver):
    """Resolver for lipid shorthand signatures using LIPID MAPS REST API.

    Converts lipid shorthand (e.g. "PC(16:0/18:1)") to LIPID MAPS ID via REST API.
    """

    name = "lipid_maps"
    identifier_type = "LM_ID"
    accepted_signatures = ["lipid_shorthand"]

    def __init__(self, config: RunConfig) -> None:
        """Initialize lipid shorthand resolver.

        Args:
            config: RunConfig instance (unused, present for API compatibility).
        """
        super().__init__(config)
        self._session = requests.Session()

    def _is_applicable(self, signature: str) -> bool:
        """Check if signature is applicable.

        Args:
            signature: The lipid shorthand string.

        Returns:
            True (all lipid_shorthand signatures are applicable).
        """
        return True

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """LIPID MAPS IDs of the lipid species (class + total composition).

        The chain-resolved shorthand cannot be queried: it contains "/",
        which LMSD's REST paths reject with 404 even URL-encoded, so it was
        silently "not found" for every acyl-specific lipid (2026-11-17). The
        species ("PC 34:1") lists every isomer; verification compares their
        structures with the molecule and keeps the right one.
        """
        query = species_shorthand(signature)
        if not query:
            return []
        url = f"https://www.lipidmaps.org/rest/compound/abbrev/{quote(query, safe='')}/lm_id"
        try:
            response = self._session.get(url, timeout=30)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            return _lm_ids(response.json())[:MAX_CANDIDATES]
        except ValueError:
            return []  # not JSON: no record
        except Exception as exc:
            raise IdentifierResolutionError(f"[Identifier] LIPID MAPS lookup failed: {exc}")

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """Resolve lipid shorthand to similar identifiers.

        Not implemented for lipid shorthand. Returns empty list.

        Args:
            signature: Lipid shorthand string.
            working_directory: Unused.

        Returns:
            Empty list.
        """
        return []
