"""GitHub #19: the Desmond/OPLS C-terminal N-methylamide cap 'NMA' is a
terminal cap like AMBER 'NME' — it must not enter a sequence as 'X'."""
import pytest

from src_new.signatures.generators.fasta import resname_to_one_letter


@pytest.mark.parametrize("cap", ["ACE", "NME", "NMA"])
def test_peptide_caps_emit_no_letter(cap):
    assert resname_to_one_letter(cap) == ""


def test_standard_residue_still_maps():
    assert resname_to_one_letter("ALA") == "A"
