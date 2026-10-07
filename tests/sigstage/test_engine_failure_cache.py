"""Acceptance tests for A1 / F-7 (pair-cache poisoning fix) and the
A1.1 amendment (in-run negative memoization).

SimEngine._entity_sim must NEVER persist sim=0.0 on resolution failure
(LookupError or generic Exception). Under A1 failures returned 0.0
transiently and EVERY recurrence re-ran the resolver chain. Campaign-scale
evidence (v14 rerun, 2026-10-07): campaign_stats executes sim work
single-threaded in its result-consumption loop; 6.8k warmup-ghost pairs
recurring across 14.6k entries re-chained per occurrence and froze forward
progress (observed: 60 TIME_WAIT sockets from one thread's request churn,
identifier caches +0, pair writes +0) -- attempt killed twice at ~26h
projection. A1.1 negative-memoizes failures IN MEMORY for the engine's
lifetime only: same-run recurrences return the transient zero without a
second chain; a FRESH instance still retries (disk stays clean -- the F-7
guarantee). Genuinely computed zeros still persist forever.

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


def test_lookup_error_transient_negmemo_fresh_instance_retries(tmp_path, monkeypatch):
    """A1+A1.1 acceptance: resolver raising LookupError leaves the pairs
    file untouched; same-run recurrence hits the in-memory negative memo
    (no second chain, no double-count); a FRESH instance retries and, once
    healed, persists the real value."""
    eng = _engine(tmp_path)
    state = {"fail": True, "n": 0}

    def flaky(cid):
        state["n"] += 1
        if state["fail"]:
            raise LookupError("simulated cactus/pug/idsm outage")
        return "CCO"  # both CIDs resolve to identical skeleton -> sim 1.0

    monkeypatch.setattr(vsim, "_cid_smiles", flaky)
    assert eng._entity_sim(CID_A, CID_B) == 0.0
    assert eng.unmapped == 1 and eng.errors == 0
    assert eng.pairs == {} and _pair_lines(eng.pair_path) == []  # F-7 guard

    n1 = state["n"]
    assert eng._entity_sim(CID_A, CID_B) == 0.0   # A1.1: same-run memo hit
    assert state["n"] == n1                        #   -> no second chain
    assert eng.unmapped == 1                       #   -> failure counted once
    assert eng.pairs == {} and _pair_lines(eng.pair_path) == []

    state["fail"] = False                          # resolver healed
    eng2 = _engine(tmp_path)                       # FRESH instance = retry
    assert eng2._entity_sim(CID_A, CID_B) == 1.0
    assert eng2.pairs["skel-cid:111|skel-cid:222"] == 1.0
    assert _pair_lines(eng.pair_path) == [PAIR_LINE]

    n_after = state["n"]
    assert eng2._entity_sim(CID_A, CID_B) == 1.0   # success path still caches
    assert state["n"] == n_after                   #   -> no extra calls


def test_generic_exception_transient_negmemo_and_counted(tmp_path, monkeypatch):
    """HTTP 500s / timeouts (non-LookupError) get identical treatment."""
    eng = _engine(tmp_path)
    calls = {"n": 0}

    def boom(cid):
        calls["n"] += 1
        raise RuntimeError("PUG 500 / read timeout")

    monkeypatch.setattr(vsim, "_cid_smiles", boom)
    assert eng._entity_sim(CID_A, CID_B) == 0.0
    assert eng.errors == 1 and eng.unmapped == 0
    assert eng.pairs == {} and _pair_lines(eng.pair_path) == []

    assert eng._entity_sim(CID_A, CID_B) == 0.0   # A1.1 memo hit
    assert eng.errors == 1 and calls["n"] == 1     # counted/resolved once

    monkeypatch.setattr(vsim, "_cid_smiles", lambda cid: "CCO")
    eng2 = _engine(tmp_path)                       # fresh instance heals
    assert eng2._entity_sim(CID_A, CID_B) == 1.0
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
    assert eng.unmapped == 1                # A1.1: distinct failure, counted once
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


def test_ghost_recurrence_costs_one_chain_per_run(tmp_path, monkeypatch):
    """A1.1 campaign-scale acceptance: an unresolvable pair asked 100x within
    one run must trigger exactly ONE resolver chain. (v14 runs sim in a
    single thread; per-occurrence re-chaining of 6.8k ghost pairs across a
    14.6k-entry scan is what actually stalled it.)"""
    eng = _engine(tmp_path)
    calls = {"n": 0}

    def boom(cid):
        calls["n"] += 1
        raise LookupError("ghost record / outage")

    monkeypatch.setattr(vsim, "_cid_smiles", boom)
    for _ in range(100):
        assert eng._entity_sim(CID_A, CID_B) == 0.0
    assert calls["n"] == 1          # one chain for the whole run
    assert eng.unmapped == 1
    assert eng.new_pairs == 1
    assert _pair_lines(eng.pair_path) == []


def test_negmemo_is_never_persisted_across_kinds(tmp_path, monkeypatch):
    """Disk-purity guard: an engine session that saw ONLY failures (chem +
    seq) must leave zero trace in the pair file and in self.pairs."""
    eng = _engine(tmp_path)

    def boom(cid):
        raise LookupError("cid ghost")

    monkeypatch.setattr(vsim, "_cid_smiles", boom)
    seqs = {"A1": ["AAAAAAAAAAAAAAAAAAAA"], "K2": ["KKKKKKKKKKKKKKKKKKKK"]}
    monkeypatch.setattr(vsim.SimEngine, "_seqs_of",
                        lambda self, kind, key: seqs[key])
    for _ in range(3):
        eng._entity_sim(CID_A, CID_B)                        # chem failure
        eng._entity_sim(("seq-acc", "A1"), ("seq-acc", "K2"))  # seq failure
    assert eng.unmapped == 2            # two distinct pairs, counted once each
    assert eng.errors == 0
    assert eng.pairs == {}
    assert _pair_lines(eng.pair_path) == []


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
