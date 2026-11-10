# Databases

Every database BioID searches, which molecule description it is searched
with, and where the search runs. The **key** is the name used in the run
configuration (*Advanced configuration → Databases* in the web application,
`[identifiers]` in `config.ini`, `config_json` in the REST API) and in
`results.json` under `identifiers/<molecule>/<signature>/<key>`.

Each database has two switches: `<key>` turns on the search for **identical**
entries (*Exact*), `<key>_similarity` the search for **similar** ones
(*Similar*). Where a database offers only one of the two, the other switch
has no effect.

Sources: `src_new/identification/registry.py`,
`src_new/identification/supplementary.py`, `src_new/identification/resolvers/`,
`src_new/config/loader.py` (code defaults) and `config.ini` (the web
application's settings). Checked against the code on 2026-11-10.

## How the searches are ordered

1. **First pass**: the main databases below, molecule by molecule, polymers
   before small molecules, within the identification stage's time budget.
2. **Second pass** (`run_supplementary_pass`): once every molecule has had
   its first pass, the **supplementary** databases run, then the
   **deferred** ones (`[identifiers] deferred_resolvers`, by default in
   `config.ini` the large NCBI databases `blast_nr_protein, blast_nt,
   blast_core_nt`). They get what is left of the budget, so a slow database
   can no longer use up the time the searches after it need.
3. **Verification** builds its candidate window from the first-pass evidence
   first, then appends up to `verify_top_n_supplementary` candidates that
   only the second pass found (see
   [Identification & verification](identifiers.md#stage-3-verification)).

## Main databases (first pass)

### Proteins and nucleic acids

| Key | Database | Searched with | Exact | Similar | Runs |
|---|---|---|---|---|---|
| `blast_pdb_protein` | PDB sequences (pdbaa), BLASTP | protein sequence | yes | yes | local |
| `blast_pdb_nucleic` | PDB sequences (pdbnt), BLASTN | nucleotide sequence | yes | yes | local |
| `blast_swissprot_protein` | UniProt Swiss-Prot, BLASTP | protein sequence | yes | yes | local |
| `blast_uniprot` | the same Swiss-Prot database (no separate UniProt database is configured; counted as one evidence source with the row above) | protein sequence | yes | yes | local |
| `blast_nr_protein` | NCBI nr, BLASTP — **deferred** in `config.ini` | protein sequence | yes | yes | local |
| `blast_core_nt` | NCBI core_nt, BLASTN — **deferred** | nucleotide sequence | yes | yes | local |
| `blast_nt` | NCBI nt, BLASTN — **deferred** | nucleotide sequence | yes | yes | local |
| `pdb_struct_protein` | RCSB PDB structure search | protein structure (PDB) | yes (≥ 99.9 % structural similarity) | yes | remote (RCSB) |
| `pdb_struct_nucleotide` | RCSB PDB structure search | nucleic-acid structure | yes | skipped: RCSB rejects pure nucleic-acid similarity queries; recorded as `na_mode_unsupported`, not as an error | remote (RCSB) |
| `mmcif_struct` | RCSB PDB structure search | mmCIF of the molecule | — | yes | remote (RCSB) |
| `alphafind_struct` | AlphaFind (AlphaFold DB) | Cα model | yes | yes | remote |
| `foldseek_3di` | Foldseek against AlphaFold DB / Swiss-Prot | Cα model | — | yes | local Foldseek; the public Foldseek server if the local search fails |

BLAST exact matches need e-value ≤ `exact_match_max_evalue`, identity ≥
`exact_match_min_identity_p` and query coverage ≥
`exact_match_min_query_cov_p` (`[blast]`; defaults 1e-50, 0.99, 0.99);
similar matches use the `similarity_match_*` thresholds. Short queries
(under 30 residues) use the short-sequence BLAST task. RCSB structure
searches fetch the query structure from this deployment's public `/files`
route (see [API](api.md#the-rcsb-file-serving-contract)).

### Small molecules, lipids, glycans, ions

| Key | Database | Searched with | Exact | Similar | Runs |
|---|---|---|---|---|---|
| `pubchem_struct` | PubChem (PUG-REST identity and 2D similarity) | SMILES / SELFIES | yes | yes (Tanimoto ≥ `[pubchem] similarity_threshold`, 95) | remote |
| `chembl_struct` | ChEMBL (EBI web services) | SMILES / SELFIES | yes | yes (≥ `[chembl] similarity_threshold`, 60) | remote |
| `idsm_pubchem`, `idsm_chembl`, `idsm_chebi` | PubChem, ChEMBL and ChEBI through the IDSM SPARQL endpoint (ELIXIR CZ) | SMILES / SELFIES | yes | yes (≥ `[idsm] similarity_threshold`, 80) | remote |
| `inchikey_pubchem` | PubChem, InChIKey → CID | InChIKey | yes | — | local PubChem mirror first, then PubChem / IDSM |
| `inchikey_self` | the InChIKey itself as a candidate (structure fetched at verification) | InChIKey | yes | — | local |
| `formula_local` (listed as `formula_pubchem_local`) | local PubChem mirror, formula → CIDs | molecular formula | yes | — | local; only when the mirror database exists |
| `formula_pubchem` | PubChem fast-formula search | molecular formula | yes | — | remote |
| `formula_chembl` | ChEMBL, formula → IDs | molecular formula | yes | — | local ChEMBL mirror first, else EBI REST; built only when `formula_chembl` is on or `VALIDATION_SKIP_PUG=1` (set on the production workers) |
| `formula_hfamily` | PubChem, formula with ±4 hydrogens (protonation states) | molecular formula | — | yes (candidates only) | local PubChem mirror first, else PubChem |
| `lipid_maps` | LIPID MAPS | lipid shorthand, e.g. `PC(16:0/18:1)` | yes | — | remote |
| `glycan_composition` | GlyCosmos → GlyTouCan | glycan composition | yes | — | remote |
| `atom` | the chemical element | element of a one-atom molecule | yes | — | local |
| `name_ccd`, `name_maps`, `name_manual` | name tables (PDB Chemical Component Dictionary, LIPID MAPS names, a curated list) → InChIKey | residue / molecule / chain names | yes | — (switch off by default) | local (`databases/*.json`) |

Formula and similarity searches only *propose* candidates: every chemical
candidate must pass the skeleton-fingerprint check at verification
(Tanimoto ≥ 0.7 between the simulated molecule and the database structure).

`pubchem_struct`, `formula_pubchem` and `formula_hfamily` sit behind a
PubChem circuit breaker: while PubChem's REST service does not answer a probe
(re-checked every 30 s), they are skipped, except `formula_hfamily` when it
can answer from the local mirror. `VALIDATION_PUBCHEM_BREAKER=0` disables the
breaker.

## Supplementary databases (second pass)

Added 2026-11-09. They can only add candidates and corroboration. In code
they are **off** (`src_new/config/loader.py`), so a configuration that does
not name them — such as the MDDBR validation configurations — is unaffected;
the web application's `config.ini` turns them on. Each is skipped, with a
warning in the log, while its data is missing.

| Key | Database | Searched with | Exact | Similar | Runs |
|---|---|---|---|---|---|
| `blast_uniref50` | UniRef50 (UniProtKB clustered at 50 %), BLASTP; cluster representatives reported as UniProt accessions | protein sequence | yes | yes | local; own `[blast] uniref50_num_threads` and `uniref50_timeout_s` |
| `foldseek_pdb` | Foldseek against a local PDB database | Cα model | — (switch off in `config.ini`) | yes | local only, never the public server |
| `swisslipids` | SwissLipids | InChIKey (first two blocks) or lipid shorthand | yes | yes (first InChIKey block: other stereo) | local index |
| `chebi_local` | ChEBI | InChIKey | yes | yes (first block) | local index; pools with `idsm_chebi` |
| `sifts_uniprot` | SIFTS PDB-chain → UniProt mapping | the PDB chains `blast_pdb_protein` matched exactly | yes | — | local index; `sifts_mode = corroborate` adds them as UniProt candidates, `xref` only records the mapping under `identification/sifts/` |

## Local data

The local databases live on the `/app/databases` volume of the workers
(paths in `[blast]`, `[pubchem]`, `[chembl]`, `[foldseek]` and
`[identifiers] *_db`). They are built or refreshed by the Jobs in `k8s/`:

| Data | Job / script |
|---|---|
| BLAST databases (pdbaa, pdbnt, Swiss-Prot, nr, nt, core_nt) | `k8s/blast-db-download-job.yaml`, `scripts/download-databases.sh` |
| UniRef50 BLAST database | `k8s/uniref50-blastdb-job.yaml` |
| Foldseek AlphaFold/Swiss-Prot and PDB databases | `k8s/foldseek-db-seed-job.yaml`, `k8s/foldseek-pdb-db-job.yaml` |
| PubChem mirror (SQLite) | `k8s/pubchem-mirror-build-job.yaml`, `scripts/populate_pubchem_mirror.py` |
| ChEMBL mirror (SQLite) | `scripts/build_chembl_local_mirror.py` |
| SIFTS, SwissLipids, ChEBI indexes | `k8s/reference-indexes-job.yaml`, `scripts/build_reference_indexes.py` |
| Name tables (`databases/ccd.json` …) | `scripts/build_ccd_json.py` |

Snapshot dates used by the g1 validation campaign (November 2026): BLAST
databases 2026-07-20 to 07-28, PubChem mirror 2026-11-04. Later refreshes are
not recorded here; check the volume.
