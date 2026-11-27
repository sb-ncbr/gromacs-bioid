"""dm1 audit (I5): a CA-only / coarse-grained protein is described by its
residue sequence and unverified leads; all-atom proteins are not."""
import shutil
from pathlib import Path

import pytest

mda = pytest.importorskip("MDAnalysis")

from tests.src_new.loader.test_chainless_topology_w31 import _run_results  # noqa: E402
from src_new.results.descriptions import _leads, describe_bead_proteins

PDB = Path(__file__).resolve().parents[1] / "data" / "charmm_psf_pdb" / "system.pdb"


class _Facade:
    def __init__(self, ag):
        self.ag = ag

    def get_fragment(self, name):
        return self.ag


def _protein(tmp_path, ca_only):
    u = mda.Universe(str(PDB))
    prot = u.select_atoms("protein and name CA" if ca_only else "protein")
    if prot.n_atoms == 0:
        pytest.skip("fixture has no protein")
    return prot


@pytest.mark.parametrize("ca_only,expected", [(True, 1), (False, 0)])
def test_bead_models_only(tmp_path, ca_only, expected):
    prot = _protein(tmp_path, ca_only)
    data = {"fragments": {"segments": [{"segment": "P", "type": "protein"}]},
            "identifiers": {"P": {"ca_only_pdb": {"foldseek_3di@sim": {"hits": [["Q06187", 97.4]]}},
                                  "name_chain": {"name_ccd": {"hits": ["KFIWNSGDRAITKG-DJLDLDEBSA-N"]}}}}}
    out = describe_bead_proteins(_Facade(prot), data)
    assert len(out) == expected
    if out:
        d = out[0]
        assert d["state"] == "described" and d["representation"] == "CA-only"
        assert len(d["sequence"]) == len(prot.residues) and "X" not in d["sequence"]
        assert [lead["identifier"] for lead in d["leads"]] == ["Q06187"]  # no chemistry leads
        assert d["leads"][0]["verified"] is False


def test_leads_dedup_and_rank():
    ids = {"topology_less_pdb": {"pdb_struct_protein@sim": {"hits": [["3P08", 100.0], ["3OCT", 99.4]]}},
           "mmcif": {"mmcif_struct@sim": {"hits": [["3P08", 100.0], ["3K54", 96.5]]}}}
    assert [h["identifier"] for h in _leads(ids)] == ["3P08", "3OCT", "3K54"]


def test_ca_only_pipeline_has_description(tmp_path):
    import dataclasses
    import json
    import multiprocessing
    from src_new.api.tasks import _run_pipeline_child
    from src_new.config.loader import RunConfig
    prot = _protein(tmp_path, True)
    inp = tmp_path / "input"
    inp.mkdir()
    prot.write(str(inp / "model_CA.pdb"))
    cfg = RunConfig.from_default_ini()
    for f in dataclasses.fields(cfg.identifiers):  # offline: no resolvers
        if isinstance(getattr(cfg.identifiers, f.name), bool):
            setattr(cfg.identifiers, f.name, False)
    cfg.to_ini_path(str(tmp_path / "config.ini"))
    _a, b = multiprocessing.Pipe(duplex=False)
    _run_pipeline_child("t", str(inp), str(tmp_path / "results.json"), str(tmp_path / "config.ini"), b)
    data = json.loads((tmp_path / "results.json").read_text())["data"]
    (d,) = data["descriptions"]
    assert d["state"] == "described" and d["sequence"] and d["leads"] == []
