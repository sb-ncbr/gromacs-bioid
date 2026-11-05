"""g1 (2026-11-05): RCSB structure search rejects large query assemblies.

Live probe on a 4-chain MDposit system (45,652 atoms, 2,872 residues,
every chain collapsed to label 'A'): the whole file -> HTTP 400 "We could
not process your search request" (or a gateway timeout); correct chain
labels -> still 400; one chain -> 200 with the right family on top.
Oversized queries are split per distinct chain and the hits merged.

No live network: resolvers' single-query step is mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

pytest.importorskip("requests")

from src_new.config.loader import RunConfig
from src_new.identification.resolvers._rcsb_search import (
    merge_hit_lists,
    split_oversized_query,
)
from src_new.identification.resolvers.mmcif import MmCifResolver
from src_new.identification.resolvers.pdb_struct import PDBStructResolver


def _chain(n_res, label, z, resnames=("ALA",), start_serial=1):
    """Backbone-only chain; peptide C(i)-N(i+1) = 1.4 A, chains 50 A apart."""
    lines, serial = [], start_serial
    for i in range(n_res):
        rn = resnames[i % len(resnames)]
        for k, name in enumerate(("N", "CA", "C")):
            x = 3.8 * i + 1.2 * k
            lines.append("ATOM  %5d  %-3s %3s %1s%4d    %8.3f%8.3f%8.3f  1.00  0.00           %s"
                         % (serial % 100000, name, rn, label, i + 1, x, 0.0, z, name[0]))
            serial += 1
    return lines


def _pdb(*chains):
    return "\n".join([ln for c in chains for ln in c] + ["END"]) + "\n"


class TestSplit:
    def test_small_query_untouched(self):
        text = _pdb(_chain(100, "A", 0.0))
        assert split_oversized_query(text) == [text]

    def test_labelled_chains_split_and_deduplicated(self):
        a = _chain(800, "A", 0.0, ("ALA", "GLY"))
        b = _chain(800, "B", 50.0, ("ALA", "GLY"))   # same sequence as A
        c = _chain(600, "C", 100.0, ("LEU",))
        out = split_oversized_query(_pdb(a, b, c))
        assert len(out) == 2
        labels = [{ln[21] for ln in t.splitlines() if ln.startswith("ATOM")} for t in out]
        assert labels == [{"A"}, {"C"}]  # largest first, B deduplicated

    def test_collapsed_label_split_at_backbone_breaks(self):
        # MDposit topology-less: every chain labelled 'A', numbering continuous
        a = _chain(900, "A", 0.0, ("ALA",))
        b = _chain(900, "A", 50.0, ("LEU",))
        out = split_oversized_query(_pdb(a, b))
        assert len(out) == 2
        n_atoms = sorted(sum(ln.startswith("ATOM") for ln in t.splitlines()) for t in out)
        assert n_atoms == [2700, 2700]

    def test_chain_cap_and_tiny_fragments(self):
        chains = [_chain(400, lab, 50.0 * i, (rn,))
                  for i, (lab, rn) in enumerate(zip("ABCDEF", ("ALA", "GLY", "LEU", "VAL", "SER", "THR")))]
        chains.append(_chain(5, "G", 400.0, ("TRP",)))   # peptide below the floor
        out = split_oversized_query(_pdb(*chains))
        assert len(out) == 4

    def test_merge_keeps_best_score(self):
        assert merge_hit_lists([[("1ABC", 70.0), ("2DEF", 50.0)],
                                [("1ABC", 80.0), ("3GHI", 60.0)]]) == \
            [("1ABC", 80.0), ("3GHI", 60.0), ("2DEF", 50.0)]


def _config():
    cfg = RunConfig()
    cfg.pdb.use_deployment_file_access = True
    cfg.pdb.deployment_file_url = "https://bioid.example"
    return cfg


BIG = _pdb(_chain(900, "A", 0.0, ("ALA",)), _chain(900, "A", 50.0, ("LEU",)))


class TestResolvers:
    def test_pdb_struct_queries_each_chain_and_merges(self, tmp_path):
        r = PDBStructResolver(_config(), as_protein=True, as_nucleotide=False)
        hits = iter([[("4FNU", 90.0), ("3MI6", 70.0)], [("3MI6", 85.0)]])
        with mock.patch.object(PDBStructResolver, "_similarity_one",
                               side_effect=lambda *a, **k: next(hits)) as one:
            out = r._resolve_similarity(BIG, str(tmp_path))
        assert one.call_count == 2
        assert out == [("4FNU", 90.0), ("3MI6", 85.0)]

    def test_mmcif_partial_failure_is_not_an_error(self, tmp_path):
        r = MmCifResolver(_config())

        def one(self, text, fmt, wd, _calls=[]):
            _calls.append(1)
            if len(_calls) == 1:
                self._last_error = "structure_search_unavailable: HTTP 500"
                return []
            return [("4FNU", 90.0)]

        with mock.patch("src_new.identification.resolvers.mmcif._mmcif_text_to_pdb",
                        return_value=BIG), \
                mock.patch.object(MmCifResolver, "_similarity_one", one):
            out = r._resolve_similarity("data_x\n", str(tmp_path))
        assert out == [("4FNU", 90.0)]
        assert r._last_error is None

    def test_mmcif_all_chains_failed_keeps_error(self, tmp_path):
        r = MmCifResolver(_config())

        def one(self, text, fmt, wd):
            self._last_error = "structure_search_unavailable: HTTP 400"
            return []

        with mock.patch("src_new.identification.resolvers.mmcif._mmcif_text_to_pdb",
                        return_value=BIG), \
                mock.patch.object(MmCifResolver, "_similarity_one", one):
            out = r._resolve_similarity("data_x\n", str(tmp_path))
        assert out == []
        assert r._last_error == "structure_search_unavailable: HTTP 400"
