# results.json reference

Every run writes one JSON document with everything BioID found and how it got
there. Download it with

```bash
curl -o results.json https://bioid-ceitec.dyn.cloud.e-infra.cz/api/v1/runs/$RUN_ID/download/results.json
```

It is large (1–5 MB for a small system, more for big ones). For the answer
alone — which molecule is what — read [`data.verification`](#dataverification-the-identifications);
the REST API also serves the parts separately (`/molecules`, `/verification`,
`/identifiers`, `/signatures`, `/download/results.csv`).

## Top level

```text
{
  "created_at": "2026-11-08T23:50:46+00:00",
  "updated_at": "…",
  "pipeline":  { run_id, run_name, status, started_at, finished_at, input_kind, preset?, … },
  "tasks":     { <task_id>: { name, status, started_at, finished_at, summary } },
  "warnings":  [ { code, message, severity, step_id, details, recorded_at } ],
  "critical_errors": [ … same shape … ],
  "events":    [ { kind, timestamp, task_id, step_name } ],
  "artifacts": { <uuid>: { step_id, kind, description, path } },
  "data":      { … the results, below … }
}
```

| Key | Meaning |
|---|---|
| `pipeline.status` | `queued`, `running`, `success`, `failed` or `cancelled`. Results are complete only at `success`. |
| `pipeline.input_kind` | What was uploaded, e.g. `pdb`, `gromacs_tpr`, `amber`. |
| `pipeline.preset` | The preset the run was submitted with, if any. |
| `pipeline.retention` | `{"policy": "default"}` (30 days after the run finished), `{"policy": "days", "days": N}` or `{"policy": "preserve"}`. |
| `pipeline.creator_ip_hash`, `pipeline.owner_token_sha256` | A keyed hash of the submitter's network address and the hash of the run's owner token (not the token). Removed from the API download. |
| `tasks` | One entry per pipeline stage, in order: `discover_input`, `load_simulation`, `repair_topology`, `unwrap_periodic_boundaries`, `analyze_universe`, `generate_signatures`, `identify_molecules`, `verify_results`, `export_results`, `render_png`. `status` is `success`, `warning` (finished, with something to report) or `failed`; `summary` holds a few counts. A `summary.partial: true` means the stage hit its time budget and the results of that stage are incomplete. |
| `warnings` | Things worth knowing, with a stable `code` (e.g. `insufficient_bonds`, `stage_time_budget`) and `details`. |
| `artifacts` | Files the run produced (mmCIF exports, PNG renders); `path` is server-side — the same files are served under `/files/<run_id>/<file>`. |

## Molecules and segments

BioID splits the system into **segments**, one per distinct molecule. A
segment is named after the chain or segment it came from (`A`, `PROA`,
`MEMB`). Ligands, ions and water that share a chain with a polymer are split
off into **virtual segments** named `<parent>__v<N>` (`A__v1`, `A__v2`, …).
Identical copies (e.g. 128 POPC lipids, 4 subunits) are grouped: the segment
is analysed once and `copies` says how many there are. Every per-molecule
section below is keyed by segment name.

### `data.fragments`

| Key | Meaning |
|---|---|
| `segments` | List of `{segment, type, copies, atoms_per_copy}` — the molecule list of the run. `type` is `protein`, `nucleic`, `small_molecule`, `lipid`, `ion`, `water` or `unknown`. |
| `type_counts` | Number of distinct molecules per type. |
| `unique` | One record per distinct molecule (key is a composition fingerprint): `molecule_type`, `segment_names`, `chain_ids`, `resnames`, `atom_count`, `element_composition`, `copy_count`. |
| `total_fragment_count` | Connected fragments in the system, all copies counted. |
| `metals` | Metal atoms found and their context. |

`data.molecules` repeats the counts (`count`, `unique_count`, `type_counts`,
`system.atom_count`); `data.universe.segments.<seg>.properties` has the
structural facts of each segment (atom, residue and bond counts, `is_protein`,
`is_nucleic`, …) and `data.universe.parameters` those of the whole system.

## `data.signatures` — what was searched for

`data.signatures.<seg>.generated` maps a **signature generator** to the
description it produced from the structure, which is what the databases are
searched with:

| Generator | Value |
|---|---|
| `fasta_map_protein`, `fasta_resname_protein`, `fasta_map_nucleic`, `fasta_resname_nucleic` | Sequence (one-letter). A generator can emit one sequence per chain as `generator[label]`. |
| `smiles`, `smiles_not_sanitized`, `inchi_key`, `selfies`, `fingerprint`, `morgan_fingerprint`, `skeleton_fp` | Chemical descriptions of small molecules. |
| `molecular_formula`, `molecular_formula_heavy` | Formula with / without hydrogens. |
| `pdb_*`, `mmcif`, `topology_less_pdb`, `ca_only_pdb` | Structure (as file text) for structure search. |
| `name_chain`, `name_molecule`, `name_segment`, `resname` | Names from the topology. |
| `lipid_shorthand`, `glycan_composition`, `atom`, `tdi` | Lipid, glycan, single-atom and other descriptions. |

`attempted` lists every generator tried, `flags` notes about the input
(`h_inferred`: hydrogens were added; `xbond_capped`: bonds to other molecules
were capped).

## `data.identifiers` — raw database hits

`data.identifiers.<seg>.<generator>.<resolver>` is one database search: the
signature from `<generator>` sent to `<resolver>` (a database client; a
`@sim` suffix means a similarity search, otherwise exact).

```text
"identifiers": { "A": { "fasta_map_protein": {
    "blast_pdb_protein": {
      "signature": "IVGGYTCGANTV…",        # what was searched
      "signature_type": "residue_sequence_protein",
      "hit_type": "identity",             # or "similarity"
      "ident_type": "PDB_ID",             # kind of identifier in hits
      "hits": ["4GUX_A", "4GUX_B", …],     # database identifiers, best first
      "hits_metadata": { "4GUX_A": { "evalue": 2.8e-162, "bit_score": 449.5,
                                     "identity_p": 1.0, "coverage_p": 1.0 } }
    },
    "attempted": ["blast_pdb_protein", "blast_uniprot", …]
} } }
```

These are candidates, not answers: use `data.verification`. Searches that
failed are listed in `data.stage_errors.identifiers.<seg>` as
`{generator, resolver, error}` (e.g. a BLAST time-out).

## `data.verification` — the identifications

This is the result. `data.verification.<seg>.verified_hits` is the list of
candidates for that molecule after each was checked against its database
record:

| Field | Meaning |
|---|---|
| `identifier`, `database`, `ident_type` | The candidate, e.g. `1AQ7` / `pdb` / `PDB_ID`, `P00760` / `uniprot` / `UNIPROT_ID`, `2332` / `pubchem` / `PUBCHEM_CID`. |
| `name`, `organism` | From the database record, when known. |
| `hit_type` | `identity` (exact match) or `similarity` (homologue / analogue). |
| `is_verified` | The candidate was re-fetched and agrees with the molecule. **Only verified hits are identifications.** |
| `final_confidence` | 0–100. ≥ 80 high, 50–80 medium, below 50 low (the web application's labels). |
| `belief` | 0–100: how strongly the database evidence agrees on this candidate (consensus across independent searches). |
| `similarity_score` | 0–100: how closely the molecule matches the record (sequence identity × coverage, fingerprint Tanimoto, or TM-score). Details in `similarity_details`. |
| `annotation_quality_score` | 0–100: completeness of the database record. |
| `resolver_score` | 0–100: the best score any search gave this candidate. |
| `supporting_evidence_count` | Number of independent searches that found it. |
| `equivalence_class_id` | Candidates with the same id are the same molecule in different databases (e.g. a PDB entry and its UniProt accession share a sequence reference). |
| `rejection_reason` | Why an unverified candidate was not verified (`below_similarity_floor`, `fingerprint_mismatch`, …). |

!!! warning "Sort by confidence"
    `verified_hits` is **not** ordered by confidence. To get the best
    identification of a molecule, take the hits with `is_verified: true` and
    sort them by `final_confidence`, highest first.

`final_confidence` combines the three terms with the weights in
`data.verification._meta`:

```text
final_confidence = w_r·belief + w_s·similarity_score + w_a·annotation_quality_score
_meta.confidence_formula   "w_r*belief + w_s*match + w_a*annotation"
_meta.weights_effective    [0.4, 0.4, 0.2]   # after normalisation to sum 1
```

`class_sizes` counts the verified candidates per `equivalence_class_id`.

## Other sections

| Key | Meaning |
|---|---|
| `data.config` | The full configuration the run used (server defaults + preset + your changes). |
| `data.input`, `data.loading` | Which files were recognised and how they were loaded (`final_strategy`, attempts). |
| `data.repair`, `data.pbc` | What was repaired in the topology (guessed elements, bonds) and how periodic boundaries were unwrapped. |
| `data.exports`, `data.render` | Exported mmCIF files and PNG renders; `render.segment_selectors` maps each segment to chains and atom ranges in `system.mmcif`. |
| `data.identification._meta`, `data.run_health` | Cache statistics and stage timings, for diagnostics. |

## Recipes

Best identification of every molecule (Python):

```python
import json
r = json.load(open("results.json"))
for seg in r["data"]["fragments"]["segments"]:
    hits = r["data"]["verification"].get(seg["segment"], {}).get("verified_hits", [])
    best = max((h for h in hits if h.get("is_verified")),
               key=lambda h: h["final_confidence"], default=None)
    print(seg["segment"], seg["type"], seg["copies"],
          best and (best["database"], best["identifier"], best.get("name"),
                    round(best["final_confidence"], 1)))
```

The same with `jq`:

```bash
jq -r '.data.verification | to_entries[] | select(.key != "_meta")
       | [.key, ((.value.verified_hits | map(select(.is_verified))
                 | max_by(.final_confidence)) // {} | .database, .identifier, .final_confidence)]
       | @tsv' results.json
```
