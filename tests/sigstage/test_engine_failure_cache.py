"""Acceptance tests for A1 / F-7 (pair-cache poisoning fix).

SimEngine._entity_sim must NEVER persist sim=0.0 on resolution failure
(LookupError or generic Exception). Failures are transient -- counted and
retried on the next call/run -- while genuinely computed zeros still cache
forever. F-7 evidence: ~90% of the organic "rerank-loss" cohort was stale
cached zeros from transient resolver outages made permanent by the
persistence bug (see lookup/s0-signature-stage-case-file.md F-7).

Offline: resolver functions are monkeypatched; the skeleton-FP and
alignment primitives themselves run for real, and the pair file is a
tmp_path artifact -- the live NFS cache is never touched.
"""
import importlib.util
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_vsim():
    spec = importlib.util.spec_from_file_location(
        "validation_similarity_a1", os.path.join(REPO, "scripts", "validation_similarity.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vsim = _load_vsim()

CID_A = ("skel-cid", "111")
CID_B = ("skel-cid", "222")
PAIR_LINE = "skel-cid:111|skel-cid:222\t1.000000"


def _engine(tmp_path, budget=400):
    """SimEngine isolated from any live cache: tmp pair file, empty memory."""
    eng = vsim.SimEngine(budget=budget)
    eng.pair_path = str(tmp_path / "pairs.jsonl")
    eng.pairs = {}
    return eng


def _pair_lines(path):
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return [ln.rstrip("\n") for ln in fh if ln.strip()]


def test_lookup_error_is_transient_and_second_call_retries(tmp_path, monkeypatch):
    """A1 acceptance: resolver raising LookupError leaves the pairs file
    untouched, and a later call RE-RESOLVES (no stale cached zero)."""
    eng = _engine(tmp_path)
    state = {"fail": True, "n": 0}

    def flaky(cid):
        state["n"] += 1
        if state["fail"]:
            raise LookupError("simulated cactus/pug/idsm outage")
        return "CCO"  # both CIDs resolve to identical skeleton -> sim 1.0

    monkeypatch.setattr(vsim, "_cid_smiles", flaky)
    got = eng._entity_sim(CID_A, CID_B)
    assert got == 0.0                        # transient zero for THIS call only
    assert eng.unmapped == 1 and eng.errors == 0
    assert eng.pairs == {}                   # not in the in-memory cache either
    assert _pair_lines(eng.pair_path) == []  # NOT persisted (this was the F-7 bug)

    state["fail"] = False                    # resolver healed
    got2 = eng._entity_sim(CID_A, CID_B)     # must retry, not read a cached 0.0
    assert got2 == 1.0
    assert eng.pairs["skel-cid:111|skel-cid:222"] == 1.0
    assert _pair_lines(eng.pair_path) == [PAIR_LINE]

    n_after = state["n"]
    assert eng._entity_sim(CID_A, CID_B) == 1.0   # success path still caches
    assert state["n"] == n_after                  # -> no extra resolver calls


def test_generic_exception_is_transient_and_counted(tmp_path, monkeypatch):
    """HTTP 500s / timeouts (non-LookupError) get the same treatment."""
    eng = _engine(tmp_path)
    calls = {"n": 0}

    def boom(cid):
        calls["n"] += 1
        raise RuntimeError("PUG 500 / read timeout")

    monkeypatch.setattr(vsim, "_cid_smiles", boom)
    assert eng._entity_sim(CID_A, CID_B) == 0.0
    assert eng.errors == 1 and eng.unmapped == 0
    assert eng.pairs == {} and _pair_lines(eng.pair_path) == []

    assert eng._entity_sim(CID_A, CID_B) == 0.0   # retry re-attempts...
    assert eng.errors == 2 and calls["n"] >= 2

    monkeypatch.setattr(vsim, "_cid_smiles", lambda cid: "CCO")
    assert eng._entity_sim(CID_A, CID_B) == 1.0   # ...and heals + persists
    assert _pair_lines(eng.pair_path) == [PAIR_LINE]


def test_computed_zero_from_successful_resolution_still_persists(tmp_path, monkeypatch):
    """Overcorrection guard: a genuinely COMPUTED 0.0 (both structures
    resolved, fingerprints taken, Tanimoto happens to be zero) must still be
    persisted and must cache-hit on the next call -- otherwise every rerun
    would recompute unresolvable-but-successful pairs. Resolution and FP
    computation run for real; only the final Tanimoto value is stubbed at 0.0
    to make the distinguishing case deterministic (real near-zero FPs are not
    guaranteed bit-disjoint)."""
    eng = _engine(tmp_path)
    calls = {"n": 0}
    monkeypatch.setattr(vsim, "_cid_smiles", lambda cid: "CCO" if cid == "111" else "c1ccccc1")

    def zero_tanimoto(a, b):
        calls["n"] += 1
        return 0.0

    monkeypatch.setattr(vsim, "_sk_tanimoto", zero_tanimoto)
    got = eng._entity_sim(CID_A, CID_B)
    assert got == 0.0
    assert eng.errors == 0 and eng.unmapped == 0   # a SUCCESS, not a failure
    assert eng.pairs["skel-cid:111|skel-cid:222"] == 0.0
    assert _pair_lines(eng.pair_path) == ["skel-cid:111|skel-cid:222\t0.000000"]

    assert eng._entity_sim(CID_A, CID_B) == 0.0    # cache hit: no recompute
    assert calls["n"] == 1


def test_empty_alignment_is_unmapped_and_transient(tmp_path, monkeypatch):
    """Discovered edge (pinned empirically): two sequences with NO alignable
    identity do not yield a computed zero -- Biopython's aligner returns no
    alignments, `align(...)[0]` raises IndexError (a LookupError subclass),
    and the pair is classified UNMAPPED. Under A1 that means transient, not
    a persisted zero. This is the seq-space analog of an unresolvable GT."""
    eng = _engine(tmp_path)
    seqs = {"A1": ["AAAAAAAAAAAAAAAAAAAA"], "K2": ["KKKKKKKKKKKKKKKKKKKK"]}
    monkeypatch.setattr(vsim.SimEngine, "_seqs_of",
                        lambda self, kind, key: seqs[key])
    got = eng._entity_sim(("seq-acc", "A1"), ("seq-acc", "K2"))
    assert got == 0.0
    assert eng.unmapped == 1 and eng.errors == 0
    assert eng.pairs == {} and _pair_lines(eng.pair_path) == []


def test_budget_counts_distinct_first_attempts_not_recurrences(tmp_path, monkeypatch):
    """Grounding for the _attempted set: on an outage day, a recurring failed
    pair must not re-burn the resolution budget on every recheck (otherwise a
    few hot ligands would exhaust it and the rest of the run would soft-zero).
    Distinct pairs keep today's one-count-per-pair semantics."""
    eng = _engine(tmp_path, budget=2)

    def always_fail(cid):
        raise LookupError("outage")

    monkeypatch.setattr(vsim, "_cid_smiles", always_fail)
    for _ in range(3):
        assert eng._entity_sim(CID_A, CID_B) == 0.0
    assert eng.unmapped == 3
    assert eng.new_pairs == 1                      # recurrence did not re-count

    monkeypatch.setattr(vsim, "_cid_smiles", lambda cid: "CCO")  # healed
    ok = eng._entity_sim(("skel-cid", "333"), ("skel-cid", "444"))
    assert ok == 1.0                               # within budget: resolves
    assert eng.new_pairs == 2

    calls = {"n": 0}

    def counting(cid):
        calls["n"] += 1
        return "CCO"

    monkeypatch.setattr(vsim, "_cid_smiles", counting)
    blocked = eng._entity_sim(("skel-cid", "555"), ("skel-cid", "666"))
    assert blocked == 0.0 and eng.errors == 1      # budget gate still blocks...
    assert calls["n"] == 0                         # ...BEFORE any resolver call


def test_identity_shortcut_performs_no_io(tmp_path, monkeypatch):
    """ka == kb returns 1.0 with no resolver call and no disk write (unchanged)."""
    eng = _engine(tmp_path)
    monkeypatch.setattr(vsim, "_cid_smiles",
                        lambda cid: pytest.fail("resolver must not be called"))
    assert eng._entity_sim(CID_A, CID_A) == 1.0
    assert eng.new_pairs == 0 and _pair_lines(eng.pair_path) == []


def test_public_sim_path_canonical_key_and_cache_hit(tmp_path, monkeypatch):
    """End-to-end at the public API: PUBCHEM* types normalize to skel-cid,
    and reversed operand order hits the same canonical pair key."""
    eng = _engine(tmp_path)
    monkeypatch.setattr(vsim, "_cid_smiles", lambda cid: "CCO")
    assert eng.sim("PUBCHEM_CID", "cid:111", "PUBCHEM_ID", "222") == 1.0

    calls = {"n": 0}

    def counting(cid):
        calls["n"] += 1
        return "CCO"

    monkeypatch.setattr(vsim, "_cid_smiles", counting)
    assert eng.sim("PUBCHEM_ID", "222", "PUBCHEM_CID", "cid:111") == 1.0
    assert calls["n"] == 0
    assert _pair_lines(eng.pair_path) == [PAIR_LINE]
