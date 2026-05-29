import json

from ...src.loader.results_file import ResultsFile


def test_results_file_writes_machine_readable_json_with_current_annotation_shape(tmp_path):
    path = tmp_path / "results.json"
    results = ResultsFile(str(path))

    results.set_item("summary/simulation_mmcif", "simulation.mmcif")
    results.set_item("summary/segments/Protein/simulation_mmcif", "Protein.mmcif")
    results.set_item("summary/segments/Protein/macromolecule_type/protein", True)
    results.set_item("summary/segments/Protein/macromolecule_type/nucleic", False)
    results.set_item("summary/segments/Protein/macromolecule_type/lipid", False)
    results.set_item("summary/segments/Protein/macromolecule_type/carbohydrate", False)
    results.set_item("summary/segments/Protein/macromolecule_type/atom", False)
    results.set_item("summary/segments/Protein/macromolecule_type/water", False)
    results.set_item("summary/segments/Protein/macromolecule_type/unknown", False)
    results.set_item("summary/segments/Protein/ident", "1ABC_A")
    results.set_item("summary/segments/Protein/ident_type", "PDB_ID")
    results.set_item("summary/segments/Protein/confidence", 95.0)
    results.set_item(
        "summary/segments/Protein/verification",
        [["1ABC_A", "PDB_ID", 95.0, 98.5], ["2XYZ_A", "PDB_ID", 90.0, None]],
    )
    results.set_item(
        "identifiers/Protein/FASTA_MAP_PROTEIN/BLAST_PDB_PROT",
        {
            "signature": "MAGA",
            "hit_type": "PDB_ID",
            "hits": [["1ABC_A", 95.0], ["2XYZ_A", 90.0]],
        },
    )
    results.set_item("signatures/Protein/generated/FASTA_MAP_PROTEIN", "MAGA")

    payload = json.loads(path.read_text())
    protein = payload["summary"]["segments"]["Protein"]

    assert payload["summary"]["simulation_mmcif"] == "simulation.mmcif"
    assert protein["simulation_mmcif"] == "Protein.mmcif"
    assert protein["macromolecule_type"]["protein"] is True
    assert protein["ident"] == "1ABC_A"
    assert protein["ident_type"] == "PDB_ID"
    assert protein["confidence"] == 95.0
    assert protein["verification"] == [
        ["1ABC_A", "PDB_ID", 95.0, 98.5],
        ["2XYZ_A", "PDB_ID", 90.0, None],
    ]

    candidate_block = payload["identifiers"]["Protein"]["FASTA_MAP_PROTEIN"]["BLAST_PDB_PROT"]
    assert candidate_block == {
        "signature": "MAGA",
        "hit_type": "PDB_ID",
        "hits": [["1ABC_A", 95.0], ["2XYZ_A", 90.0]],
    }


def test_results_file_serialization_order_is_stable_for_golden_outputs(tmp_path):
    path = tmp_path / "ordered.json"
    results = ResultsFile(str(path))

    results.set_item("summary/segments/A/ident", "first")
    results.set_item("summary/segments/A/confidence", 100.0)
    results.set_item("summary/segments/B/ident", "second")

    assert path.read_text() == (
        "{\n"
        '    "summary": {\n'
        '        "segments": {\n'
        '            "A": {\n'
        '                "ident": "first",\n'
        '                "confidence": 100.0\n'
        "            },\n"
        '            "B": {\n'
        '                "ident": "second"\n'
        "            }\n"
        "        }\n"
        "    }\n"
        "}"
    )
