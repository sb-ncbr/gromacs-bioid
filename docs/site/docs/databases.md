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

The NCBI nr, nt and core_nt databases are **off by default and on in the Deep
search preset** (since 2026-11-18). nr is 826 GB on a network volume that
delivers about 50 MB/s to all workers together, so one nr search reads for
hours; at a 1-hour limit it finished 1 of 30 protein searches in a week. They
have their own per-search limit (`[blast] ncbi_timeout_s`, 12 hours), and a
run that searches them gets that much more identification time.
3. **Verification** builds its candidate window from the first-pass evidence
   first, then appends up to `verify_top_n_supplementary` candidates that
   only the second pass found (see
   [Identification & verification](identifiers.md#stage-3-verification)).

A deferred database is **skipped** for a molecule that a first-pass search
already matched exactly (≥ 0.99 identity and coverage in PDB, Swiss-Prot or
UniProt for nr; PDB nucleic for nt/core_nt): it would only re-find the same
sequence as GenBank duplicates, at hours of reading nr over NFS
(`[identifiers] skip_deferred_on_exact`, on). BLAST uses 2 threads per search
for UI runs.

## Main databases (first pass)

### Proteins and nucleic acids

| Key | Database | Searched with | Exact | Similar | Runs |
|---|---|---|---|---|---|
| `blast_pdb_protein` | PDB sequences (pdbaa), BLASTP | protein sequence | yes | yes | local |
| `blast_pdb_nucleic` | PDB sequences (pdbnt), BLASTN | nucleotide sequence | yes | yes | local |
| `blast_pdb_nucleic_dc` | the same pdbnt, discontiguous megablast, modified bases (N) count as matching (below); one evidence source with the row above | nucleotide sequence of 30 nt or more | yes | yes | local |
| `blast_swissprot_protein` | UniProt Swiss-Prot, BLASTP | protein sequence | yes | yes | local |
| `blast_uniprot` | the same Swiss-Prot database (no separate UniProt database is configured; counted as one evidence source with the row above) | protein sequence | yes | yes | local |
| `blast_nr_protein` | NCBI nr, BLASTP — **deferred**, Deep search only | protein sequence | yes | yes | local |
| `blast_core_nt` | NCBI core_nt, BLASTN — **deferred**, Deep search only | nucleotide sequence | yes | yes | local |
| `blast_nt` | NCBI nt, BLASTN — **deferred**, Deep search only | nucleotide sequence | yes | yes | local |
| `pdb_struct_protein` | RCSB PDB structure search | protein structure (PDB, also the quick-search `topology_less_pdb`) | — (RCSB scores are ranks, not an identity measure) | yes | remote (RCSB) |
| `pdb_struct_nucleotide` | RCSB PDB structure search | nucleic-acid structure (`pdb_nucleic`) | — | skipped: RCSB rejects pure nucleic-acid structure queries; recorded as `na_mode_unsupported`, not as an error (also when the quick-search `topology_less_pdb` of a nucleic acid reaches `pdb_struct_protein`) | remote (RCSB) |
| `mmcif_struct` | RCSB PDB structure search | mmCIF of the molecule | — | yes | remote (RCSB) |

RCSB structure search cannot process large queries: a structure above 1,500
residues or 12,000 atoms is searched without hydrogens, then chain by chain
(chains found from chain labels, or from breaks between consecutive residues:
peptide or phosphodiester bond, CA–CA over 4.2 Å, P–P over 8 Å). A chain still
above the limit is not sent; when no chain fits, the search records
`query_too_large`, a skip, not an error.
| `alphafind_struct` | AlphaFind (AlphaFold DB) | Cα model | yes | yes | remote |
| `foldseek_3di` | Foldseek against AlphaFold DB / Swiss-Prot | Cα model | — | yes | local Foldseek; the public Foldseek server if the local search fails |

A BLAST hit is an exact match when it is the same molecule by absolute
measures, for proteins and nucleic acids alike: identity ≥ 0.99, query
coverage ≥ 0.99 (`exact_match_min_identity_p`, `exact_match_min_query_cov_p`
can only raise these) and subject coverage ≥ 0.9. A lower subject coverage
is accepted only when the unaligned part of the database sequence is at its
ends (at most 25 residues at each end, no internal gap over 5: expression
tags, unmodelled termini); UniProt and Swiss-Prot entries need an aligned
length of at least 50 residues instead. A nucleic-acid hit must align on the
same strand (the reverse complement is the partner strand). Nucleic acids of
up to 25 nt match exactly only a database sequence of the same length
(identity and coverage ≥ 0.9).

PDB sequences (pdbnt) store a modified nucleotide as `N`: a tRNA has one every
8–10 nt (1EHZ chain A, yeast tRNA-Phe: 15 in 76). BLAST counts `N` as a
mismatch, and megablast cannot start an alignment between them, so
`blast_pdb_nucleic` never matches such a chain exactly. `blast_pdb_nucleic_dc`
searches the same database with discontiguous megablast (both 16-nt templates)
and computes identity with `N` as matching: a column where one sequence has
`N` and the other a base counts as identical, other bases must be identical
and gaps count against identity, and at most 25 % of the aligned columns may
be such `N` columns (more is no evidence: BLAST's own identity is kept). The
alignment is extended over `N` columns at its ends (an alignment never starts
on an `N`). The rest of the exact-match rule is the one above; similar matches
are scored with the same identity. In the simulated sequence a modified
nucleotide (PSU, 5MC, OMG, …) is `X`, searched as `N`; a sequence that contains
one is searched with BLASTN (11-nt words) instead, since discontiguous
megablast cannot use a query word with an `N`. Under 30 nt only
`blast_pdb_nucleic` searches (short-sequence task). For the unmodified yeast
tRNA-Phe sequence, `blast_pdb_nucleic` matches 19 PDB chains exactly (the
unmodified ones), `blast_pdb_nucleic_dc` 89, 1EHZ among them.
E-value and bit score are not used for exact matches (they grow with the
query length, so a perfect 30–100 nt match could never pass a fixed cut-off);
`exact_match_max_evalue` and `exact_match_min_bits` are kept for old configs
and no longer change anything. Similar matches use the `similarity_match_*`
thresholds. Short queries (under 30 residues) use the short-sequence BLAST
task. RCSB structure
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
| `lipid_maps` | LIPID MAPS | lipid shorthand, e.g. `PC(16:0/18:1)`, looked up as its species (`PC 34:1`; LMSD's REST paths reject the chain-level form) — every isomer is a candidate (at most 25), verification keeps the matching structure | yes | — | remote |
| `glycan_composition` | GlyCosmos → GlyTouCan | glycan composition | yes | — | remote |
| `atom` | the chemical element | element of a one-atom molecule | yes | — | local |
| `name_ccd` | PDB Chemical Component Dictionary names → InChIKey | residue / molecule / chain names | yes | — (switch off by default) | local (`databases/ccd.json`) |
| `name_maps` | Force-field names: 309 CHARMM36 / AMBER / GROMACS / Slipids residue and molecule names (lipids, sterols, detergents, fatty acids, ions) to InChIKeys, each checked against PubChem (`src_new/identification/name_tables/`) | names | — | — | candidates like any other name lookup, verified as usual; never an override |
| `name_manual` | a curated list | names | — | — | **off**: no data (`manual.json`) |

Formula and similarity searches only *propose* candidates: every chemical
candidate must pass the skeleton-fingerprint check at verification
(Tanimoto ≥ 0.7 between the simulated molecule and the database structure).

A SMILES with a valence no compound has (for example a carbon with 17
bonds, from bonds guessed on a crowded system) is not sent to `pubchem_struct`,
`chembl_struct` or the `idsm_*` searches: they record `invalid_valence`, a
skip, not an error. Bonds to metals do not count for the ligand atom, so
metal complexes (heme, chlorophyll, ferrocene, carbonyls) are searched as
usual. `pubchem_struct`, ChEMBL's REST fallback and `glycan_composition`
retry busy answers (HTTP 429, 5xx), timeouts and connection errors twice;
a query the service rejects (any other 4xx) is not retried.

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
