"""Fixtures for the BioID MCP server tests: a mocked BioID API (respx) and an
in-memory MCP client session."""
from __future__ import annotations

import json
from typing import Any

import pytest
import respx

from mcp.shared.memory import create_connected_server_and_client_session
from mcp_server.config import Settings
from mcp_server.server import build_server

API = "https://api.test"
PUBLIC = "https://bioid.test"
RUN = "1c2a4d4b-94cb-48ec-81a9-d0c0924af8bd"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    return Settings(api_url=API, public_url=PUBLIC, max_upload_bytes=1000)


@pytest.fixture
def api():
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/api/v1/capabilities").respond(
            json={"typical_duration_minutes": {"min": 2, "max": 8}, "additions": []})
        yield router


@pytest.fixture
def server(settings, api):
    return build_server(settings)


class Caller:
    def __init__(self, session):
        self.session = session

    async def __call__(self, tool: str, args: dict[str, Any] | None = None):
        res = await self.session.call_tool(tool, args or {})
        text = res.content[0].text if res.content else ""
        if res.isError:
            return True, text
        return False, json.loads(text)


@pytest.fixture
async def call(server):
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        yield Caller(session)


# -- payloads shaped like the live API (trimmed from example run 3PTB) ------

SUMMARY = {
    "run_id": RUN, "pipeline_name": "BAT3", "status": "success",
    "started_at": "2026-11-08T23:50:46.759861+00:00",
    "finished_at": "2026-11-08T23:58:37.460787+00:00", "input_kind": "pdb",
    "run_name": "Trypsin with benzamidine>Crystal structure (PDB 3PTB)",
    "task_count": 10, "warning_count": 3, "error_count": 0,
}

MOLECULES = {
    "run_id": RUN, "unique_molecules": {}, "type_counts": {}, "total_fragment_count": 0,
    "segments": ["A", "A__v1", "A__v2", "A__v3", "B"],
    "segment_meta": {
        "A": {"type": "protein", "atom_count": 1629, "residue_count": 223, "copies": 1,
              "display_name": "A", "chain": None},
        "A__v1": {"type": "small_molecule", "atom_count": 9, "residue_count": 1, "copies": 1,
                  "display_name": "BEN", "chain": None},
        "A__v2": {"type": "ion", "atom_count": 1, "residue_count": 1, "copies": 1,
                  "display_name": "CA", "chain": None},
        "A__v3": {"type": "water", "atom_count": 1, "residue_count": 1, "copies": 62,
                  "display_name": "HOH", "chain": None},
        "B": {"type": "lipid", "atom_count": 50, "residue_count": 1, "copies": 10,
              "display_name": "POPC", "chain": None},
    },
}


def hit(seg, db, ident, conf, verified=True, **kw):
    base = {
        "identifier": ident, "ident_type": kw.pop("ident_type", db.upper()), "database": db,
        "segment": seg, "final_confidence": conf, "is_verified": verified,
        "rejection_reason": None if verified else kw.pop("reason", "fingerprint_mismatch"),
        "name": kw.pop("name", None), "organism": kw.pop("organism", None),
        "database_url": kw.pop("url", None), "similarity_score": kw.pop("similarity_score", None),
        "skeleton_sim": kw.pop("skeleton_sim", None), "ground_truth_override": kw.pop("gt", None),
        "equivalence_class_id": "x" * 500,
    }
    base.update(kw)
    return base


VERIFICATION = {
    "run_id": RUN, "segment": "A",
    "hits": [
        hit("A", "pdb", "1AQ7", 81.4, name="TRYPSIN", organism="Bos taurus",
            url="https://www.rcsb.org/structure/1AQ7", similarity_score=100.0),
        hit("A", "pdb", "1AUJ", 81.4, name="TRYPSIN"),
        hit("A", "uniprot", "P00760", 84.1, name="Serine protease 1", organism="Bos taurus",
            url="https://www.uniprot.org/uniprotkb/P00760", similarity_score=1.0),
        hit("A__v1", "pubchem", "2332", 80.0, name="Benzamidine", skeleton_sim=1.0),
        hit("A__v1", "pubchem", "999", 0.0, verified=False, name="Something"),
        hit("A__v2", "element", "CA", 100.0, name="Calcium ion", gt="element_monoatomic"),
        hit("A__v3", "pubchem", "962", 45.0, name="Water", similarity_score=0.5),
        # B (POPC): only rejected hits
        hit("B", "swisslipids", "SLM:1", 10.0, verified=False, reason="formula_mismatch"),
    ],
}

STATUS = {
    "run_id": RUN,
    "pipeline": {"run_id": RUN, "pipeline_name": "BAT3", "status": "success",
                 "started_at": SUMMARY["started_at"], "finished_at": SUMMARY["finished_at"],
                 "input_kind": "pdb", "input_files": None, "metadata": {}},
    "tasks": [
        {"task_id": "load_simulation", "name": "Load Simulation", "status": "success"},
        {"task_id": "identify_molecules", "name": "Identify Molecules", "status": "warning"},
        {"task_id": "verify_results", "name": "Verify Results", "status": "success"},
    ],
    "warnings": [
        {"code": "identifier_resolver_failed",
         "message": "blast_nr_protein (fasta_map_protein): BLAST timed out after 300s. Database: /app/databases/nr/nr.",
         "step_id": "identify_molecules",
         "details": {"segment": "A", "service": "blast_nr_protein"}},
        {"code": "identifier_resolver_failed",
         "message": "mmcif_struct@sim (mmcif): no_polymer_payload",
         "details": {"segment": "A__v1", "service": "mmcif_struct@sim"}},
        {"code": "pbc_unwrap_applied", "message": "unwrapped", "details": {}},
    ],
    "critical_errors": [], "events": [],
    "progress": {"molecules_done": 5, "molecules_total": 5, "per_segment": {}},
}

SIGNATURES_A = {
    "run_id": RUN,
    "signatures": [
        {"segment": "A", "generator": "fasta_map_protein", "signature": "IVGGYTCGANTVPY"},
        {"segment": "A", "generator": "pdb_protein", "signature": "ATOM      1  N   ILE ..."},
        {"segment": "A", "generator": "molecular_formula_heavy", "signature": "C1012N279O324S14"},
        {"segment": "A", "generator": "fingerprint", "signature": "c742ba69"},
    ],
    "attempted_generators": {},
}

OPTIONS = {
    "config": {"verification": {"verify_top_n": 50, "similarity_top_n": 10},
               "identifiers": {"blast_nt": True}},
    "presets": [
        {"id": "balanced", "title": "Balanced", "description": "Defaults.", "icon": "scale",
         "overrides": {}},
        {"id": "quick", "title": "Quick look", "description": "Skips slow searches.", "icon": "zap",
         "overrides": {"identifiers": {"blast_nt": False, "blast_nt_similarity": False},
                       "verification": {"verify_top_n": 30}}},
        {"id": "exact", "title": "Exact matches", "description": "No similarity.", "icon": "target",
         "overrides": {"identifiers": {"pubchem_struct_similarity": False}}},
        {"id": "deep", "title": "Deep search", "description": "Wider.", "icon": "telescope",
         "overrides": {"verification": {"verify_top_n": 150}}},
    ],
}
