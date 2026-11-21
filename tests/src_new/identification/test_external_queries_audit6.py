"""2026-11-21 (mdval audit item 6): malformed or failing external queries.

- SMILES with an impossible valence (guessed bonds: one C with 17 bonds)
  are declined before IDSM/ChEMBL/PubChem (`invalid_valence`, not
  applicable), and the services' own rejections are "rejected", not an
  outage that makes the run incomplete;
- SELFIES decoding follows the signature type;
- RCSB: chain breaks in CA-only / P-only input, chains still too large are
  not sent (`query_too_large`), 4xx bodies are logged;
- one retry helper (http_retry) for ChEMBL's fallback, GlyCosmos and PubChem.

No live network: every request is faked; sleeps are patched.
"""
from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from unittest import mock

import pytest
import requests

from src_new import http_retry
from src_new.completeness import is_incomplete
from src_new.config.loader import RunConfig
from src_new.identification.base import IdentifierResolutionError
from src_new.identification.outcomes import failure_class, is_not_applicable, is_retryable
from src_new.identification.resolvers import _rcsb_search, chembl as chembl_mod, idsm as idsm_mod
from src_new.identification.resolvers import pubchem as pubchem_mod
from src_new.identification.resolvers._rcsb_search import split_oversized_query
from src_new.identification.resolvers._smiles_query import query_smiles, refusal, valence_problem

# the audit's SMILES shape: one carbon closing 15 rings, plus its H
OVERBONDED = "C123456789%10%11%12%13%14[CH]%15" + "".join(
    f"C{r}" if r < 10 else f"C%{r}" for r in range(1, 16))


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(http_retry, "_sleep", slept.append)
    return slept


class FakeResponse:
    def __init__(self, status=200, payload=None, text=None, headers=None):
        self.status_code = status
        self._payload = payload
        self.text = text if text is not None else (json.dumps(payload) if payload is not None else "")
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error", response=self)


class Sequence:
    """Fake send: returns/raises the scripted items in order, records calls."""

    def __init__(self, *items):
        self.items = list(items)
        self.calls = []

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


# -- valence ---------------------------------------------------------------------

class TestValence:
    @pytest.mark.parametrize("smiles", [
        OVERBONDED,
        "C(C)(C)(C)(C)C",           # pentavalent carbon (ChEMBL 500, PubChem 400)
        "CC(=C)(=C)C",
        "O(C)(C)(C)C",
        "[NH2](C)(C)(C)C",
        "CF(C)",
        "[H](C)C",
    ])
    def test_impossible_valence_refused(self, smiles):
        assert valence_problem(smiles)
        assert refusal(smiles).startswith("invalid_valence: ")

    @pytest.mark.parametrize("name, smiles", [
        ("aspirin", "CC(=O)Oc1ccccc1C(=O)O"),
        ("pyridone, aromatic C=O", "O=c1cccc[nH]1"),
        ("pyrene, ring-fusion carbons", "c1cc2ccc3cccc4ccc(c1)c2c34"),
        ("tetramethylammonium", "C[N+](C)(C)C"),
        ("nitro, charge-separated", "C[N+](=O)[O-]"),
        ("nitro, pentavalent notation", "CN(=O)=O"),
        ("carbon monoxide", "[C-]#[O+]"),
        ("trimethyloxonium", "C[O+](C)C"),
        ("sulfate", "OS(=O)(=O)O"),
        ("SF6", "FS(F)(F)(F)(F)F"),
        ("PF6-", "F[P-](F)(F)(F)(F)F"),
        ("perchlorate", "[O-]Cl(=O)(=O)=O"),
        ("IF7", "FI(F)(F)(F)(F)(F)F"),
        ("XeO4", "O=[Xe](=O)(=O)=O"),
        ("heme b, Fe with 4 N", "CC1=C(CCC(O)=O)C2=CC3=C(CCC(O)=O)C(C)=C4C=C5C(C)=C(C=C)"
                               "C6=[N]5[Fe]7(N34)N8C(=CC1=[N]27)C(C)=C(C=C)C8=C6"),
        ("heme with axial His and O2, Fe with 6 neighbours",
         "CC1=C2C=C3C(C)=C(C=C)C4=[N]3[Fe]56(N2C(=C1CCC(O)=O)C=C1C(CCC(O)=O)=C(C)C(=[N]15)"
         "C=C1C(C)=C(C=C)C(=C4)N16)(N1C=CN=C1)O=O"),
        ("chlorophyll a, Mg", "CCC1=C(C)C2=[N]3C1=Cc1c(C)c4C(=O)C(C(=O)OC)C5=C6C(CCC(=O)OC/C=C(\\C)"
                              "CCCC(C)CCCC(C)CCCC(C)C)C(C)C(=[N]6[Mg]3(n14)n1c(=C2)c(C)c(C=C)c1=C6)C=5"),
        ("ferrocene, Fe bonded to 10 C",
         "[CH]12[CH]3[CH]4[CH]5[CH]1[Fe]23451678[CH]2[CH]1[CH]6[CH]7[CH]28"),
        ("uranocene, U bonded to 16 C",
         "[CH]12=[CH]3[CH]4=[CH]5[CH]6=[CH]7[CH]8=[CH]1[U]23456789%10%11%12%13%14%15"
         "[CH]9=[CH]%10[CH]%11=[CH]%12[CH]%13=[CH]%14[CH]%15=[CH]9"),
        ("iron pentacarbonyl", "O=C=[Fe](=C=O)(=C=O)(=C=O)=C=O"),
        ("cisplatin", "N[Pt](N)(Cl)Cl"),
        ("hexaaqua Mg", "O[Mg](O)(O)(O)(O)O"),
        ("bridging fluoride, AlF4- on Mg", "F[Al-](F)(F)F[Mg]"),
        ("dative bond", "C[NH2]->[Cu]"),
        ("o-carborane, C with 6 cluster bonds",
         "[BH]1[BH]2[BH]3[BH]4[BH]1[BH]1[BH]2[CH]2[BH]3[BH]4[CH]12"),
    ])
    def test_legitimate_compounds_pass(self, name, smiles):
        assert valence_problem(smiles) is None, name

    def test_unparsable_is_left_to_the_service(self):
        assert valence_problem("C1CC(") is None


class TestSignatureType:
    def test_bracket_smiles_is_not_decoded_as_selfies(self):
        assert query_smiles("CC[C@H](N)O", "smiles") == "CC[C@H](N)O"
        # all-bracket SMILES: a SELFIES only when the type says so
        assert query_smiles("[C][C][O]", "smiles") == "[C][C][O]"
        assert query_smiles("[C][C][O]", "selfies") == "CCO"

    def test_without_type_only_bracket_tokens_are_selfies(self):
        assert query_smiles("[C][C][O]", None) == "CCO"
        assert query_smiles("CC[C@H](N)O", None) == "CC[C@H](N)O"

    def test_manager_type_reaches_the_resolver(self, monkeypatch):
        sent = []
        monkeypatch.setattr(idsm_mod, "idsm_fetch_similarity_match",
                            lambda smiles, **k: sent.append(smiles) or [])
        r = idsm_mod.IDSMResolverPubchem(RunConfig())
        r.resolve("[C][C][O]", as_similarity=True, signature_type="smiles")
        r.resolve("[C][C][O]", as_similarity=True, signature_type="selfies")
        assert sent == ["[C][C][O]", "CCO"]


class TestResolversDecline:
    def _boom(self, *a, **k):
        raise AssertionError("an impossible valence must not be sent")

    def _check(self, r):
        assert r.resolve(OVERBONDED, as_similarity=True, signature_type="smiles") == []
        assert r.get_last_error().startswith("invalid_valence")
        assert is_not_applicable(r.get_last_error())

    def test_idsm(self, monkeypatch):
        monkeypatch.setattr(idsm_mod, "idsm_fetch_similarity_match", self._boom)
        self._check(idsm_mod.IDSMResolverChembl(RunConfig()))

    def test_chembl(self, monkeypatch):
        monkeypatch.setattr(chembl_mod, "chembl_fetch_similarity_match", self._boom)
        self._check(chembl_mod.ChemblResolver(RunConfig()))

    def test_pubchem_similarity_and_identity(self, monkeypatch):
        monkeypatch.setattr(pubchem_mod, "pubchem_fetch_similarity_match", self._boom)
        monkeypatch.setattr(pubchem_mod, "pubchem_fetch_identity_match", self._boom)
        cfg = RunConfig()
        cfg.pubchem.local_db_path = ""
        r = pubchem_mod.PubChemResolver(cfg)
        self._check(r)
        assert r.resolve(OVERBONDED, as_similarity=False, signature_type="smiles") == []
        assert r.get_last_error().startswith("invalid_valence")

    def test_recorded_as_not_applicable_not_as_a_warning(self):
        from src_new.pipeline_steps import _record_resolver_errors

        class Ctx:
            def __init__(self):
                self.data, self.warnings = {}, []
                self.results = SimpleNamespace(get_data=lambda p, d=None: self.data.get(p, d),
                                               set_data=self.data.__setitem__)

            def add_warning(self, *a):
                self.warnings.append(a)

        ctx = Ctx()
        _record_resolver_errors(ctx, "LIG", [
            {"resolver": "idsm_pubchem@sim", "generator": "smiles_not_sanitized",
             "error": "invalid_valence: C with 17 bonds"},
            {"resolver": "pdb_struct_protein@sim", "generator": "topology_less_pdb",
             "error": "query_too_large"}])
        assert ctx.warnings == []
        assert [s["reason"] for s in ctx.data["identification/_meta/not_applicable/LIG"]] == [
            "invalid_valence: C with 17 bonds", "query_too_large"]


class TestRejectedIsNotRetryable:
    @pytest.mark.parametrize("message", [
        "idsm_pubchem@sim (smiles): [Identifier] IDSM searching failed: QueryBadFormed: A bad "
        "request has been sent to the endpoint: probably the SPARQL query is badly formed. "
        "Response: b'... CDKException: too high atom valence'",
        "pubchem_struct@sim (smiles): [Identifier] PUBCHEM API similarity search failed: "
        "HTTP 400 PUGREST.BadRequest The given listkey is invalid",
        "chembl_struct@sim (smiles): [Identifier] CHEMBL searching failed (client and REST API): "
        'HTTP 500: {"error_message": "Problem standardizing the query molecule", "traceback": ...',
    ])
    def test_rejections(self, message):
        assert failure_class(message) == "rejected"
        assert not is_retryable(message)
        assert not is_incomplete({"warnings": [
            {"code": "identifier_resolver_failed", "message": message, "details": {"segment": "LIG"}}]})

    def test_a_real_outage_stays_retryable(self):
        assert failure_class("HTTP Error 500: Internal Server Error") == "server_error"
        assert failure_class("HTTP 503 PUGREST.ServerBusy Too many requests") == "rate_limited"
        assert is_incomplete({"warnings": [{"code": "identifier_resolver_failed",
                                            "message": "chembl_struct@sim: HTTP 500: Bad Gateway"}]})


# -- http_retry ------------------------------------------------------------------

class TestHttpRetry:
    def _run(self, monkeypatch, *items, url="https://example.org/x", **kw):
        seq = Sequence(*items)
        monkeypatch.setattr(http_retry.requests, "request", seq)
        return seq, http_retry.request("GET", url, **kw)

    def test_5xx_and_429_retried(self, monkeypatch, _no_sleep):
        seq, r = self._run(monkeypatch, FakeResponse(503), FakeResponse(429), FakeResponse(200, {}))
        assert r.status_code == 200 and len(seq.calls) == 3 and len(_no_sleep) == 2

    def test_retry_after_honoured_and_capped(self, monkeypatch, _no_sleep):
        self._run(monkeypatch, FakeResponse(429, headers={"Retry-After": "600"}), FakeResponse(200))
        assert _no_sleep == [http_retry.MAX_RETRY_AFTER_S]

    def test_gives_up_with_the_last_response(self, monkeypatch):
        seq, r = self._run(monkeypatch, FakeResponse(500), FakeResponse(502), FakeResponse(503))
        assert r.status_code == 503 and len(seq.calls) == http_retry.ATTEMPTS

    @pytest.mark.parametrize("status", [400, 401, 404, 422])
    def test_other_4xx_not_retried(self, monkeypatch, status):
        seq, r = self._run(monkeypatch, FakeResponse(status))
        assert r.status_code == status and len(seq.calls) == 1

    def test_not_found_and_rejected_5xx_not_retried(self, monkeypatch):
        seq, r = self._run(monkeypatch, FakeResponse(500, text="<h1>Page not found (404)</h1>"),
                           url="https://cactus.nci.nih.gov/chemical/structure/X/smiles")
        assert len(seq.calls) == 1
        seq, r = self._run(monkeypatch, FakeResponse(
            500, {"error_message": "Problem standardizing the query molecule"}),
            url="https://www.ebi.ac.uk/chembl/api/data/similarity/C/80.json")
        assert len(seq.calls) == 1

    def test_timeouts_retried_then_raised(self, monkeypatch):
        seq = Sequence(*[requests.exceptions.ReadTimeout("Read timed out.")] * 3)
        monkeypatch.setattr(http_retry.requests, "request", seq)
        with pytest.raises(requests.exceptions.ReadTimeout):
            http_retry.request("GET", "https://example.org/x")
        assert len(seq.calls) == 3

    def test_connection_error_then_success(self, monkeypatch):
        seq, r = self._run(monkeypatch, requests.exceptions.ConnectionError("reset by peer"),
                           FakeResponse(200))
        assert r.status_code == 200 and len(seq.calls) == 2

    def test_give_up_stops_retries(self, monkeypatch):
        seq, r = self._run(monkeypatch, FakeResponse(503), FakeResponse(200), give_up=lambda: True)
        assert r.status_code == 503 and len(seq.calls) == 1

    def test_session_is_used(self, monkeypatch):
        session = SimpleNamespace(request=Sequence(FakeResponse(200)))
        monkeypatch.setattr(http_retry.requests, "request", self._boom)
        assert http_retry.request("POST", "https://example.org", session=session).status_code == 200
        assert session.request.calls[0][2]["timeout"] == 30

    def _boom(self, *a, **k):
        raise AssertionError("session expected")


# -- PubChem ---------------------------------------------------------------------

def _pubchem(*items):
    session = SimpleNamespace(request=Sequence(*items))
    return session, RunConfig()


class TestPubChem:
    def test_listkey_polled_to_cids(self):
        session, cfg = _pubchem(
            FakeResponse(202, {"Waiting": {"ListKey": "123", "Message": "running"}}),
            FakeResponse(202, {"Waiting": {"ListKey": "123", "Message": "running"}}),
            FakeResponse(200, {"IdentifierList": {"CID": [702]}}))
        assert pubchem_mod.pubchem_fetch_identity_match("CCO", session, cfg) == ["702"]
        method, url, kw = session.request.calls[0]
        assert (method, url, kw["data"]) == ("POST", f"{pubchem_mod._PUG}/identity/smiles/JSON",
                                             {"smiles": "CCO"})
        assert session.request.calls[-1][1] == f"{pubchem_mod._PUG}/listkey/123/cids/JSON"

    def test_similarity_threshold_and_constant_scores(self):
        session, cfg = _pubchem(FakeResponse(200, {"PC_Compounds": [
            {"id": {"id": {"cid": 2244}}}, {"id": {"id": {"cid": 5161}}}]}))
        out = pubchem_mod.pubchem_fetch_similarity_match("CC(=O)Oc1ccccc1C(=O)O", 95, session, cfg)
        assert out == [("2244", 95.0), ("5161", 95.0)]
        assert "similarity/smiles/JSON?Threshold=95" in session.request.calls[0][1]

    def test_not_found_is_empty(self):
        session, cfg = _pubchem(FakeResponse(404, {"Fault": {"Code": "PUGREST.NotFound"}}))
        assert pubchem_mod.pubchem_fetch_identity_match("CCO", session, cfg) == []

    def test_timeout_raises_instead_of_empty(self):
        session, cfg = _pubchem(*[requests.exceptions.ReadTimeout("Read timed out.")] * 3)
        with pytest.raises(IdentifierResolutionError) as exc:
            pubchem_mod.pubchem_fetch_similarity_match("CCO", 95, session, cfg)
        assert failure_class(str(exc.value)) == "timeout"
        assert len(session.request.calls) == 3

    def test_search_never_finishing_raises_timeout(self, monkeypatch):
        monkeypatch.setattr(pubchem_mod, "_MAX_POLLS", 3)
        waiting = FakeResponse(202, {"Waiting": {"ListKey": "9"}})
        session, cfg = _pubchem(*[waiting] * 4)  # the search and 3 polls
        with pytest.raises(IdentifierResolutionError) as exc:
            pubchem_mod.pubchem_fetch_identity_match("CCO", session, cfg)
        assert failure_class(str(exc.value)) == "timeout"

    def test_server_busy_retried_then_raised_as_busy(self):
        busy = FakeResponse(503, {"Fault": {"Code": "PUGREST.ServerBusy", "Message": "Too many requests"}})
        session, cfg = _pubchem(busy, busy, busy)
        with pytest.raises(IdentifierResolutionError) as exc:
            pubchem_mod.pubchem_fetch_identity_match("CCO", session, cfg)
        assert failure_class(str(exc.value)) == "rate_limited"
        assert len(session.request.calls) == 3

    def test_bad_request_tries_the_fallback_then_is_rejected(self):
        bad = FakeResponse(400, {"Fault": {"Code": "PUGREST.BadRequest",
                                           "Message": "The given listkey is invalid"}})
        session, cfg = _pubchem(bad, bad)
        with pytest.raises(IdentifierResolutionError) as exc:
            pubchem_mod.pubchem_fetch_similarity_match("CCO", 95, session, cfg)
        assert "fastsimilarity_2d" in session.request.calls[1][1]
        assert failure_class(str(exc.value)) == "rejected"

    def test_bad_request_fallback_answer_kept(self):
        bad = FakeResponse(400, {"Fault": {"Code": "PUGREST.BadRequest"}})
        session, cfg = _pubchem(bad, FakeResponse(200, {"IdentifierList": {"CID": [0]}}))
        # the plain smiles->CID lookup answers CID 0 for "no such compound"
        assert pubchem_mod.pubchem_fetch_identity_match("CCO", session, cfg) == []


# -- ChEMBL fallback and GlyCosmos -----------------------------------------------

class TestChemblFallback:
    def test_retried_then_answers(self, monkeypatch):
        monkeypatch.setitem(__import__("sys").modules, "chembl_webresource_client.new_client", None)
        seq = Sequence(FakeResponse(502), FakeResponse(200, {"molecules": [
            {"molecule_chembl_id": "CHEMBL25", "similarity": "100.0"}]}))
        monkeypatch.setattr(http_retry.requests, "request", seq)
        out = chembl_mod.chembl_fetch_similarity_match("CC(=O)Oc1ccccc1C(=O)O", 80, True)
        assert out == [("25", 100.0)] and len(seq.calls) == 2

    def test_standardization_500_rejected_once(self, monkeypatch):
        monkeypatch.setitem(__import__("sys").modules, "chembl_webresource_client.new_client", None)
        seq = Sequence(FakeResponse(500, {"error_message": "Problem standardizing the query molecule"}))
        monkeypatch.setattr(http_retry.requests, "request", seq)
        with pytest.raises(IdentifierResolutionError) as exc:
            chembl_mod.chembl_fetch_similarity_match("C(C)(C)(C)(C)C", 80, True)
        assert len(seq.calls) == 1
        assert failure_class(str(exc.value)) == "rejected"


class TestGlycosmos:
    def test_retried(self):
        from src_new.identification.resolvers.glycan import GlycanCompositionResolver

        r = GlycanCompositionResolver(RunConfig())
        r._session = SimpleNamespace(request=Sequence(
            requests.exceptions.ConnectTimeout("timed out"), FakeResponse(503),
            FakeResponse(200, {"id": "G15021LG"})))
        assert r._resolve_identity("Hex(3)HexNAc(2)", "") == ["G15021LG"]
        assert len(r._session.request.calls) == 3

    def test_not_found_not_retried(self):
        from src_new.identification.resolvers.glycan import GlycanCompositionResolver

        r = GlycanCompositionResolver(RunConfig())
        r._session = SimpleNamespace(request=Sequence(FakeResponse(404)))
        assert r._resolve_identity("Hex(3)HexNAc(2)", "") == []


# -- RCSB ------------------------------------------------------------------------

def _atoms(names_xyz, label="A", resname="ALA"):
    """[(resnum, atom name, (x, y, z))] -> ATOM lines."""
    return ["ATOM  %5d  %-3s %3s %1s%4d    %8.3f%8.3f%8.3f  1.00  0.00           %s"
            % (i + 1, name, resname, label, resnum % 10000, x, y, z, name[0])
            for i, (resnum, name, (x, y, z)) in enumerate(names_xyz)]


def _ca_chain(n, z, start=1):
    return [(start + i, "CA", (3.8 * i, 0.0, z)) for i in range(n)]


def _pdb(lines):
    return "\n".join(lines + ["END"]) + "\n"


class TestRcsbSplit:
    def test_ca_only_split_at_ca_gaps(self):
        # MDR00106551 shape: one label, CA only; two chains 50 A apart
        text = _pdb(_atoms(_ca_chain(900, 0.0) + _ca_chain(900, 50.0, start=901)))
        out = split_oversized_query(text)
        assert len(out) == 1  # same sequence (ALA x 900): queried once
        assert sum(ln.startswith("ATOM") for ln in out[0].splitlines()) == 900

    def test_p_only_split_at_phosphate_gaps(self):
        p1 = [(1 + i, "P", (6.5 * i, 0.0, 0.0)) for i in range(800)]
        p2 = [(801 + i, "P", (6.5 * i, 0.0, 80.0)) for i in range(800)]
        out = split_oversized_query(_pdb(_atoms(p1 + p2, resname="  U")), max_residues=1000)
        assert len(out) == 1
        assert sum(ln.startswith("ATOM") for ln in out[0].splitlines()) == 800

    def test_unbroken_oversized_chain_is_not_sent(self):
        text = _pdb(_atoms(_ca_chain(2272, 0.0)))
        assert split_oversized_query(text) == []

    def test_only_fitting_chains_sent(self):
        big = _atoms(_ca_chain(1600, 0.0), label="A")
        small = _atoms(_ca_chain(300, 50.0), label="B", resname="GLY")
        out = split_oversized_query(_pdb(big + small))
        assert len(out) == 1 and {ln[21] for ln in out[0].splitlines() if ln.startswith("ATOM")} == {"B"}

    def test_full_backbone_still_split_by_peptide_bonds(self):
        lines = []
        for i in range(1800):
            z = 0.0 if i < 900 else 50.0
            x = 3.8 * (i % 900)
            lines += [(i + 1, "N", (x, 0.0, z)), (i + 1, "CA", (x + 1.2, 0.0, z)),
                      (i + 1, "C", (x + 2.4, 0.0, z))]
        out = split_oversized_query(_pdb(_atoms(lines)))
        assert len(out) == 1
        assert sum(ln.startswith("ATOM") for ln in out[0].splitlines()) == 2700


def _cfg():
    cfg = RunConfig()
    cfg.pdb.use_deployment_file_access = True
    cfg.pdb.deployment_file_url = "https://bioid.example"
    return cfg


class TestRcsbResolvers:
    TOO_BIG = _pdb(_atoms(_ca_chain(2272, 0.0)))

    def test_pdb_struct_records_query_too_large(self, tmp_path):
        from src_new.identification.resolvers.pdb_struct import PDBStructResolver

        r = PDBStructResolver(_cfg(), as_protein=True, as_nucleotide=False)
        with mock.patch.object(PDBStructResolver, "_similarity_one",
                               side_effect=AssertionError("must not be sent")):
            assert r.resolve(self.TOO_BIG, as_similarity=True) == []
        assert r.get_last_error() == "query_too_large"
        assert failure_class(r.get_last_error()) == "not_applicable"

    def test_mmcif_records_query_too_large(self, tmp_path):
        from src_new.identification.resolvers.mmcif import MmCifResolver

        r = MmCifResolver(_cfg())
        with mock.patch("src_new.identification.resolvers.mmcif._mmcif_text_to_pdb",
                        return_value=self.TOO_BIG), \
                mock.patch("src_new.identification.resolvers.mmcif._na_only_mmcif_payload",
                           return_value=False), \
                mock.patch("src_new.identification.resolvers.mmcif._no_polymer_mmcif_payload",
                           return_value=False), \
                mock.patch.object(MmCifResolver, "_similarity_one",
                                  side_effect=AssertionError("must not be sent")):
            assert r._resolve_similarity("data_x\n", str(tmp_path)) == []
        assert r._last_error == "query_too_large"

    def test_mmcif_sends_the_reduced_single_query(self, tmp_path):
        from src_new.identification.resolvers.mmcif import MmCifResolver

        big = _pdb(_atoms(_ca_chain(1600, 0.0)) + _atoms(_ca_chain(300, 50.0), label="B",
                                                         resname="GLY"))
        sent = []
        r = MmCifResolver(_cfg())
        with mock.patch("src_new.identification.resolvers.mmcif._mmcif_text_to_pdb",
                        return_value=big), \
                mock.patch("src_new.identification.resolvers.mmcif._na_only_mmcif_payload",
                           return_value=False), \
                mock.patch("src_new.identification.resolvers.mmcif._no_polymer_mmcif_payload",
                           return_value=False), \
                mock.patch.object(MmCifResolver, "_similarity_one",
                                  lambda self, q, fmt, wd: sent.append(q) or [("1ABC", 90.0)]):
            assert r._resolve_similarity("data_x\n", str(tmp_path)) == [("1ABC", 90.0)]
        assert len(sent) == 1 and sent[0] != big
        assert sum(ln.startswith("ATOM") for ln in sent[0].splitlines()) == 300

    def test_4xx_body_logged(self, monkeypatch, caplog):
        resp = FakeResponse(400, text='{"status":400,"message":"We could not process your search request"}')
        monkeypatch.setattr(_rcsb_search.requests, "post", lambda *a, **k: resp)
        with caplog.at_level(logging.WARNING, logger="identifier"):
            with pytest.raises(IdentifierResolutionError, match="HTTP 400"):
                _rcsb_search.post_rcsb_query({"query": {}})
        assert "We could not process your search request" in caplog.text
