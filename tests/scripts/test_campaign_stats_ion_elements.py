"""Unit tests for campaign_stats._ion_elements_of (F19 union semantics).

Pure-function tests over synthetic results.json docs:
  * token channel keeps working (halides + metals from unique keys)
  * metals channel alone is enough (coordinated-metal case: no tokens)
  * union is add-only (both channels contribute; nothing removed)
  * missing/malformed fragments sections are safe no-ops
  * non-vocab elements and non-list payloads are ignored
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..", "..", "scripts")))

import campaign_stats as cs  # noqa: E402


def _doc(unique=None, metals=None, fragments_none=False):
    if fragments_none:
        data = {}
    else:
        data = {"fragments": {}}
        if unique is not None:
            data["fragments"]["unique"] = unique
        if metals is not None:
            data["fragments"]["metals"] = metals
    return {"data": data}


class TestTokenChannel:
    def test_tokens_from_unique_keys(self):
        doc = _doc(unique={
            "type:lipid|atoms:100|residues:2|elements:C=40,H=80,Cl=2": {},
            "type:protein|atoms:50|residues:5|elements:C=20,Zn=1": {},
        })
        assert cs._ion_elements_of(doc) == {"Cl", "Zn"}

    def test_non_vocab_excluded(self):
        doc = _doc(unique={
            "type:small_molecule|atoms:10|residues:1|elements:C=5,He=1,X=2": {},
        })
        assert cs._ion_elements_of(doc) == set()


class TestMetalsChannel:
    def test_metals_only(self):
        doc = _doc(unique={"type:protein|atoms:100|residues:9|"
                           "elements:C=40,H=60,N=10,O=12": {}},
                   metals={"schema": 1, "present_elements": ["Zn"],
                           "element_atom_counts": {"Zn": 1}, "atoms": []})
        assert cs._ion_elements_of(doc) == {"Zn"}

    def test_union_add_only(self):
        doc = _doc(unique={
            "type:lipid|atoms:100|residues:2|elements:C=40,H=80,Cl=2": {},
        }, metals={"present_elements": ["Zn", "Ca"]})
        assert cs._ion_elements_of(doc) == {"Cl", "Zn", "Ca"}

    def test_metals_non_vocab_and_garbage_ignored(self):
        doc = _doc(metals={"present_elements": ["He", "Zn", None, 42]})
        assert cs._ion_elements_of(doc) == {"Zn"}

    def test_metals_present_elements_not_list(self):
        doc = _doc(metals={"present_elements": "Zn"})
        # string is iterable but must not explode; worst case adds nothing
        out = cs._ion_elements_of(doc)
        assert isinstance(out, set)


class TestRobustness:
    def test_no_fragments_section(self):
        assert cs._ion_elements_of(_doc(fragments_none=True)) == set()

    def test_fragments_unique_not_dict(self):
        doc = {"data": {"fragments": {"unique": ["not-a-dict"]}}}
        assert cs._ion_elements_of(doc) == set()

    def test_metals_missing_key(self):
        doc = _doc(unique={
            "type:lipid|atoms:5|residues:1|elements:Cl=1": {}})
        assert cs._ion_elements_of(doc) == {"Cl"}

    def test_empty_doc(self):
        assert cs._ion_elements_of({}) == set()

    def test_pre_f19_results_noop(self):
        """A results.json written before F19 has no fragments/metals; the
        union must be a strict no-op (no-move regression guarantee)."""
        doc = _doc(unique={
            "type:protein|atoms:60|residues:6|elements:C=30,H=40,K=1": {},
        })
        assert cs._ion_elements_of(doc) == {"K"}
