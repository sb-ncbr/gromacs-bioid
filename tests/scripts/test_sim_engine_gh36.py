"""GitHub #36: one similarity engine (the stats copy re-exports the F-7
engine) and opt-in revalidation of cached zeros."""
import importlib.util
import os
import sys

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_stats_copy_is_the_main_engine():
    stats = _load(os.path.join(SCRIPTS, "stats", "validation_similarity.py"), "vsim_stats")
    assert hasattr(stats.SimEngine(budget=0), "_negmemo")  # the F-7 engine


def _engine(tmp_path, monkeypatch, cached, seqs, revalidate):
    vs = _load(os.path.join(SCRIPTS, "validation_similarity.py"), "vsim_main")
    eng = vs.SimEngine.__new__(vs.SimEngine)
    eng.pairs, eng.new_pairs, eng.budget, eng.unmapped, eng.errors = dict(cached), 0, 10, 0, 0
    eng._aligner, eng._attempted, eng._negmemo = None, set(), {}
    eng.pair_path = str(tmp_path / "pairs.jsonl")
    eng.revalidate_zeros, eng._revalidated = revalidate, set()
    eng.zeros_revalidated = eng.zeros_changed = 0
    monkeypatch.setattr(eng, "_seqs_of", lambda kind, key: seqs(key))
    return eng


KEY = "seq:A|seq:B"


def test_cached_zero_trusted_by_default(tmp_path, monkeypatch):
    eng = _engine(tmp_path, monkeypatch, {KEY: 0.0}, lambda k: ["MKT"], revalidate=False)
    assert eng._entity_sim(("seq", "A"), ("seq", "B")) == 0.0


def test_revalidated_zero_is_recomputed_and_appended(tmp_path, monkeypatch):
    eng = _engine(tmp_path, monkeypatch, {KEY: 0.0}, lambda k: ["MKTAYIAK"], revalidate=True)
    assert eng._entity_sim(("seq", "A"), ("seq", "B")) > 0.9
    assert eng.zeros_changed == 1
    assert (tmp_path / "pairs.jsonl").read_text().startswith(KEY + "\t")


def test_failed_revalidation_keeps_cached_value(tmp_path, monkeypatch):
    def boom(k):
        raise LookupError("down")
    eng = _engine(tmp_path, monkeypatch, {KEY: 0.0}, boom, revalidate=True)
    assert eng._entity_sim(("seq", "A"), ("seq", "B")) == 0.0
    assert eng.pairs[KEY] == 0.0 and not (tmp_path / "pairs.jsonl").exists()
