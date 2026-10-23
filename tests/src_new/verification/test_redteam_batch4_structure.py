"""Red-team batch-4 (5.1) — D-13 structure-worker latent defects + fetcher routing
+ similarity floors.

D-13 pins (all empirically anchored):
  1. CA extraction is MODEL 1 only and PER CHAIN — no NMR-ensemble or
     multimer chimera traces.
  2. TM-score is normalized by the QUERY length: tmtools ground truth for a
     12-residue perfect continuation of a 60-residue reference is
     tm_norm_chain1 = 1.0, tm_norm_chain2 = 0.2 (probed 2026-10-23); the
     reference-normalized value is kept additively in details.
  3. Large entries that lack a .pdb file fall back to .cif (mmCIF), parsed
     via gemmi with the same per-chain semantics.
  4. The sequence-proxy fallback returns None on failure (never a fabricated
     0.0 that still counts as "a score"), and materializes no alignment list.
Routing pins: get_fetcher(ident_type, signature_type) routes PDB_ID to the
structure fetcher for structure signatures and to the sequence fetcher for
fasta signatures (the registry-order bug that made every structure hit
tm:0.0).
Floor pins (known issue #2): a degenerate similarity score (0.0-TM, near-zero
identity) can never count as positive evidence.
"""

from __future__ import annotations

import math
from unittest.mock import Mock, patch

import numpy as np
import pytest

from src_new.verification.fetchers.sequence_fetcher import SequenceSignatureFetcher
from src_new.verification.fetchers.structure_fetcher import StructureSignatureFetcher
from src_new.verification.fetchers.compound_fetcher import CompoundSignatureFetcher
from src_new.verification.registry import get_default_registry
from src_new.verification.workers.structure_worker import StructureVerificationWorker


# --------------------------------------------------------------------------
# synthetic structure builders
# --------------------------------------------------------------------------

def _helix(n: int, phase: float = 0.0, rise: float = 1.5) -> np.ndarray:
    """Ideal alpha-helix CA trace (matches the tmtools ground-truth probe)."""
    pts = []
    for i in range(n):
        t = phase + i * 1.745
        pts.append([2.3 * math.cos(t), 2.3 * math.sin(t), rise * i])
    return np.array(pts, dtype=float)


def _atom(serial: int, name: str, resname: str, chain: str, resid: int,
          x: float, y: float, z: float) -> str:
    element = name.strip()[0]
    return (f"ATOM  {serial:5d} {name:^4s} {resname:>3s} {chain:1s}{resid:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2s}")


def _chain_lines(chain: str, coords: np.ndarray, resname: str,
                 serial_start: int = 1) -> tuple[list[str], int]:
    lines, serial = [], serial_start
    for i, (x, y, z) in enumerate(coords, start=1):
        for aname, (dx, dy, dz) in (("N", (-0.5, 0.0, 0.0)),
                                    ("CA", (0.0, 0.0, 0.0)),
                                    ("C", (0.5, 0.0, 0.0)),
                                    ("O", (1.0, 0.0, 0.0))):
            lines.append(_atom(serial, aname, resname, chain, i,
                               x + dx, y + dy, z + dz))
            serial += 1
    return lines, serial


def _pdb(*chains: tuple[str, np.ndarray, str], models: int = 1) -> str:
    """Build a PDB string; chains may repeat across MODEL blocks."""
    out = ["HEADER    SYNTHETIC BATCH-4 FIXTURE"]
    if models == 1:
        serial = 1
        for chain, coords, resname in chains:
            lines, serial = _chain_lines(chain, coords, resname, serial)
            out += lines
            out.append("TER")
    else:
        for m in range(1, models + 1):
            out.append(f"MODEL     {m:4d}")
            serial = 1
            for chain, coords, resname in chains[m - 1]:  # type: ignore[index]
                lines, serial = _chain_lines(chain, coords, resname, serial)
                out += lines
                out.append("TER")
            out.append("ENDMDL")
    out.append("END")
    return "\n".join(out) + "\n"


def _mmcif(chain: str, coords: np.ndarray, resname: str) -> str:
    rows = []
    serial = 1
    for i, (x, y, z) in enumerate(coords, start=1):
        for aname in ("N", "CA", "C", "O"):
            element = aname.strip()[0]
            off = {"N": -0.5, "CA": 0.0, "C": 0.5, "O": 1.0}[aname]
            rows.append(f"ATOM {serial} {element} {aname} . {resname} {chain} {i} "
                        f"{x + off:.3f} {y:.3f} {z:.3f} 1.00 0.00 1")
            serial += 1
    body = "\n".join(rows)
    return f"""data_synth
#
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_alt_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
_atom_site.occupancy
_atom_site.B_iso_or_equiv
_atom_site.pdbx_PDB_model_num
{body}
#
"""


# --------------------------------------------------------------------------
# D-13 defect 1: model-1-only, per-chain extraction
# --------------------------------------------------------------------------

class TestD13ModelOnePerChainExtraction:
    def test_model1_only_no_nmr_chimera(self):
        worker = StructureVerificationWorker()
        text = _pdb(
            (("A", _helix(12), "ALA"),),          # MODEL 1: 12-res chain
            (("A", _helix(30, phase=3.0), "GLY"),),  # MODEL 2: junk ensemble member
            models=2)
        traces = worker._extract_ca_chains(text)
        assert traces is not None
        assert len(traces) == 1, traces  # not the 42-residue chimera
        chain_id, seq, coords = traces[0]
        assert chain_id == "A"
        assert len(seq) == 12
        assert set(seq) == {"A"}
        assert coords.shape == (12, 3)

    def test_multichain_kept_separate(self):
        worker = StructureVerificationWorker()
        text = _pdb(("A", _helix(12), "ALA"), ("B", _helix(12, phase=1.0), "GLY"))
        traces = worker._extract_ca_chains(text)
        assert traces is not None and len(traces) == 2, traces
        by_chain = {c: (s, xyz) for c, s, xyz in traces}
        assert set(by_chain) == {"A", "B"}
        assert set(by_chain["A"][0]) == {"A"}
        assert set(by_chain["B"][0]) == {"G"}
        for seq, xyz in by_chain.values():
            assert len(seq) == 12 and xyz.shape == (12, 3)


# --------------------------------------------------------------------------
# D-13 defect 2: TM normalized by query length (tmtools ground truth:
# 12-res perfect continuation of 60-res reference -> norm1 1.0, norm2 0.2)
# --------------------------------------------------------------------------

class TestD13QueryLengthNormalization:
    def test_domain_fragment_scores_by_query_length(self):
        worker = StructureVerificationWorker()
        query = _pdb(("A", _helix(12), "ALA"))
        canonical = _pdb(("A", _helix(60), "ALA"))
        score = worker.verify(query, "9XXX", "PDB_ID", canonical,
                              signature_type="pdb_protein")
        assert score is not None
        assert score.metric_name == "tm_score"
        assert score.normalized_score >= 95.0, score  # was ~20 with tm_norm_chain2
        ref_norm = score.details.get("tm_score_ref_normalized")
        assert ref_norm is not None
        assert ref_norm < 50.0, f"ref-normalized should expose the dilution: {ref_norm}"

    def test_identical_structure_still_100(self, minimal_pdb):
        worker = StructureVerificationWorker()
        score = worker.verify(minimal_pdb, "9XXX", "PDB_ID", minimal_pdb,
                              signature_type="pdb_protein")
        assert score is not None
        assert score.normalized_score >= 99.0


# --------------------------------------------------------------------------
# D-13 defects 4+5: proxy never fabricates 0.0; failures propagate as None
# --------------------------------------------------------------------------

class TestD13ProxyFailureSemantics:
    def test_unparsable_canonical_returns_none(self, minimal_pdb):
        worker = StructureVerificationWorker()
        assert worker.verify(minimal_pdb, "9XXX", "PDB_ID",
                             "NOT A STRUCTURE AT ALL",
                             signature_type="pdb_protein") is None

    def test_empty_canonical_returns_none(self, minimal_pdb):
        worker = StructureVerificationWorker()
        assert worker.verify(minimal_pdb, "9XXX", "PDB_ID", "",
                             signature_type="pdb_protein") is None

    def test_proxy_still_scores_without_tmtools(self, minimal_pdb):
        from src_new.verification.workers import structure_worker as sw
        worker = StructureVerificationWorker()
        with patch.object(sw, "_TMTOOLS_AVAILABLE", False):
            score = worker.verify(minimal_pdb, "9XXX", "PDB_ID", minimal_pdb,
                                  signature_type="pdb_protein")
        assert score is not None
        assert score.metric_name == "structure_sequence_proxy"
        assert score.normalized_score >= 99.0


# --------------------------------------------------------------------------
# fetcher routing (the known bug: PDB_ID always got the sequence fetcher)
# --------------------------------------------------------------------------

class TestFetcherRouting:
    def test_structure_signature_routes_to_structure_fetcher(self):
        registry = get_default_registry()
        fetcher = registry.get_fetcher("PDB_ID", signature_type="pdb_protein")
        assert isinstance(fetcher, StructureSignatureFetcher)

    def test_fasta_signature_routes_to_sequence_fetcher(self):
        registry = get_default_registry()
        fetcher = registry.get_fetcher("PDB_ID", signature_type="fasta_protein")
        assert isinstance(fetcher, SequenceSignatureFetcher)

    def test_legacy_call_unchanged(self):
        """Default (signature-type-less) routing keeps historical order."""
        registry = get_default_registry()
        assert isinstance(registry.get_fetcher("PDB_ID"), SequenceSignatureFetcher)
        assert isinstance(registry.get_fetcher("PUBCHEM_CID"),
                          CompoundSignatureFetcher)
        assert isinstance(registry.get_fetcher("UNIPROT_ID"),
                          SequenceSignatureFetcher)


# --------------------------------------------------------------------------
# D-13 defect 3: .pdb absent for large entries -> .cif fallback
# --------------------------------------------------------------------------

class TestCifFallback:
    @patch("src_new.verification.fetchers.structure_fetcher.rcsb_cache.get_cached")
    def test_pdb_404_falls_back_to_cif(self, mock_get):
        cif_text = _mmcif("A", _helix(8), "ALA")
        mock_get.side_effect = [Mock(status_code=404, text=""), Mock(status_code=200, text=cif_text)]
        out = StructureSignatureFetcher().fetch("1ABC", "PDB_ID")
        assert out == cif_text
        urls = [c.args[0] for c in mock_get.call_args_list]
        assert urls[0].endswith("/1ABC.pdb") and urls[1].endswith("/1ABC.cif")

    @patch("src_new.verification.fetchers.structure_fetcher.rcsb_cache.get_cached")
    def test_pdb_ok_returned_directly(self, mock_get):
        pdb_text = _pdb(("A", _helix(8), "ALA"))
        mock_get.return_value = Mock(status_code=200, text=pdb_text)
        out = StructureSignatureFetcher().fetch("1ABC", "PDB_ID")
        assert out == pdb_text
        assert mock_get.call_count == 1

    @patch("src_new.verification.fetchers.structure_fetcher.rcsb_cache.get_cached")
    def test_both_missing_returns_none(self, mock_get):
        mock_get.return_value = Mock(status_code=404, text="")
        assert StructureSignatureFetcher().fetch("9ZZZ", "PDB_ID") is None
        assert mock_get.call_count == 2


# --------------------------------------------------------------------------
# mmCIF signatures are parseable worker input
# --------------------------------------------------------------------------

class TestMmcifSupport:
    def test_mmcif_content_extracts_chains(self):
        worker = StructureVerificationWorker()
        traces = worker._extract_ca_chains(_mmcif("A", _helix(10), "ALA"))
        assert traces is not None and len(traces) == 1
        chain_id, seq, coords = traces[0]
        assert len(seq) == 10 and coords.shape == (10, 3)

    def test_mmcif_signature_type_applicable(self):
        worker = StructureVerificationWorker()
        assert worker.is_applicable("mmcif", "PDB_ID") is True


# --------------------------------------------------------------------------
# known issue #2: degenerate similarity scores never count as evidence
# --------------------------------------------------------------------------

class TestSimilarityFloors:
    def test_floor_helper_exists_and_maps_metrics(self):
        from src_new.verification.models import similarity_meets_floor
        assert similarity_meets_floor("tm_score", 100.0) is True
        assert similarity_meets_floor("tm_score", 0.0) is False       # degenerate
        assert similarity_meets_floor("structure_sequence_proxy", 0.0) is False
        assert similarity_meets_floor("seq_identity_coverage", 12.0) is False
        # unknown metric names pass (chemicals/elements keep their own gates)
        assert similarity_meets_floor("multi_fingerprint_tanimoto", 0.0) is True

    def test_floor_thresholds_conservative(self):
        from src_new.verification import models
        assert models.SIMILARITY_FLOORS["tm_score"] <= 30.0
        assert models.SIMILARITY_FLOORS["structure_sequence_proxy"] <= 25.0
        assert models.SIMILARITY_FLOORS["seq_identity_coverage"] <= 25.0
