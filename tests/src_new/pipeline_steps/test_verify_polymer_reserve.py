"""dm1 audit (I2): small segments verify first (b33), but the polymers keep
a reserved share of the verify budget so many small segments cannot starve
them (zenodo/14060756: 63 lipid fragments, protein never verified)."""
from src_new.pipeline_steps import POLYMER_VERIFY_RESERVE, _with_polymer_reserve

SUMMARY = [{"segment": "PROA", "type": "protein"}, {"segment": "DNA", "type": "nucleic"}] + \
          [{"segment": f"L{i}", "type": "lipid"} for i in range(10)]
ITEMS = [(f"L{i}",) for i in range(10)] + [("PROA",), ("DNA",)]


class Clock:
    def __init__(self, t, step):
        self.t, self.step = t, step

    def __call__(self):
        self.t += self.step
        return self.t


def _order(deadline, clock):
    return [it[0] for it in _with_polymer_reserve(ITEMS, SUMMARY, deadline, clock)]


def test_no_deadline_keeps_order():
    assert _order(None, Clock(0, 1)) == [it[0] for it in ITEMS]


def test_no_polymers_keeps_order():
    items = ITEMS[:10]
    assert [it[0] for it in _with_polymer_reserve(items, SUMMARY, 100.0, Clock(0, 1))] == [i[0] for i in items]


def test_polymers_jump_ahead_when_reserve_reached():
    # 100 s budget, each small segment "takes" 10 s: after ~6 the reserve (40 s) is reached
    out = _order(100.0, Clock(0, 10))
    i = out.index("PROA")
    assert out[i:i + 2] == ["PROA", "DNA"]
    assert 0 < i < 10 and set(out) == {it[0] for it in ITEMS}


def test_plenty_of_time_polymers_after_all_small():
    out = _order(1e9, Clock(0, 0.001))
    assert out[-2:] == ["PROA", "DNA"]
