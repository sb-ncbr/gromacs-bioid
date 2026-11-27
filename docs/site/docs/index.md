# Using BioID

BioID reads the files of a molecular dynamics simulation and reports which
molecules it contains — proteins, nucleic acids, ligands, ions, lipids,
glycans — with matching database entries and a confidence for each match.
The public instance is
[bioid-ceitec.dyn.cloud.e-infra.cz](https://bioid-ceitec.dyn.cloud.e-infra.cz/).

There are three ways to use it:

- the **web application** (this page),
- the **[REST API](#rest-api)** for scripts and pipelines,
- the **[MCP server](mcp.md)** for AI assistants such as Claude.

## Submitting a simulation

On the front page, drop your files into **Annotation request** (or use
*Browse files*), optionally name the run, and press **Start annotation**.

| Engine | Files |
|---|---|
| GROMACS | `.tpr`, or `.top` with its `.itp` includes, plus `.gro` coordinates (or the first frame of a `.xtc`/`.trr`/`.dcd`) |
| AMBER | `.prmtop`/`.parm7` plus `.rst7`/`.inpcrd`/`.nc`/`.mdcrd` coordinates (or the first frame of a `.dcd`/`.trr`/`.xtc`) |
| CHARMM / NAMD | `.psf` plus `.pdb`/`.crd`/`.coor` coordinates (or the first frame of a `.dcd`/`.xtc`/`.trr`/`.nc`) |
| Desmond | a `.cms` (or `.mae`) system file |
| LAMMPS | a single `.data` file |
| Structures | `.pdb` / `.cif`, or a `.gro` alone |
| Bundles | `.zip` / `.tar` / `.tar.gz` of the above |

A topology without coordinates is accepted too: the molecules are identified
from the topology (sequences, chemistry), but structure searches and
stereochemistry are skipped, and the run says so.

Each file may be up to 128 MiB, and one submission up to 128 MiB in total.
BioID analyses the starting structure, so
you do not need to upload a trajectory.

A run takes from a few minutes (a small structure) to about an hour (a large
system with many distinct molecules, with every database searched). You can
close the page: runs submitted from your network address are listed under
**Your annotations**, where you can open, rerun or delete them.

!!! tip "Try it without uploading"
    The **Example analyses** at the bottom of the front page are finished runs
    you can open directly.

## Presets and advanced configuration

**Advanced configuration → Edit** opens the run settings. Start from a
preset, then fine-tune if you need to:

| Preset | What it does | When to use it |
|---|---|---|
| **Balanced** (default) | Every database except NCBI nr, nt and core_nt; exact and similar matches. | Most runs. |
| **Quick look** | Skips the slowest searches (NCBI nr/nt, UniRef50, the AlphaFind, Foldseek and RCSB structure searches) and verifies 30 candidates per molecule instead of 100. | A first look at a large system; minutes rather than up to an hour. |
| **Exact matches** | Every similarity search is off; only identical database entries are reported. | You expect known molecules and do not want homologues or analogues. |
| **Deep search** | Also searches NCBI nr, nt and core_nt (up to 12 hours per search); verifies 150 candidates per molecule (plus 60 from the supplementary databases) and keeps 20 similar matches; also searches mixed protein/nucleic-acid PDB complexes. | Unusual or engineered molecules where the best match is not obvious. Can take many hours. |

Below the presets you can change individual settings:

- **Databases** — for each database, whether it is searched for identical
  entries (*Exact*) and for similar ones (*Similar*). The
  [Databases](databases.md) page says what each one searches.
- **Verification** — how many candidates per molecule are checked against
  their database records, how many similar matches are kept, the minimum
  confidence for a match to be marked verified, and the weights of the three
  confidence terms.
- **BLAST**, **ChEMBL**, **IDSM**, **PubChem** — when a sequence or chemical
  match counts as exact or as similar.
- **PDB**, **Signatures**, **Loader** — structure search and how the files
  are read.

Settings that belong to the deployment (database locations, programs,
service addresses, parallelism) cannot be changed per run.

## Reading the results {#reading-the-results}

The run page lists the molecules found on the left and shows the selected
molecule (or the whole system) on the right: its best identification, the
database entries that match it, and how sure BioID is about each.

### Molecules {#molecules}

BioID splits the simulated system into molecules from the bonds in your
files. Identical copies (500 waters, 12 copies of one lipid) are one row with
a copy count. Each molecule has a **kind** — protein, nucleic acid, lipid,
small molecule, ion, water or other — from its residues and composition, and
the list can be grouped by kind or by how well the molecule was identified.

### Confidence {#confidence}

How sure BioID is that a database entry is the molecule in your simulation,
from 0 to 100. It combines three measured terms:

- **agreement** — how many independent database searches proposed the entry
  (one exact search gives 50, two give 75; it never reaches 100 by itself);
- **match** — how closely the entry matches your molecule: sequence identity
  × coverage, structural TM-score or chemical-skeleton similarity;
- **annotation** — how complete the database record is.

The weights are 40 / 40 / 20 by default. A term that could not be measured is
left out rather than counted as zero. The labels are **High** (80–100,
reliable), **Medium** (50–79, worth a quick check) and **Low** (under 50, a
lead, not an answer). **Exact** marks single-atom ions matched by element and
water matched by rule. The formula is on
[Identification & verification](identifiers.md#stage-3-verification).

### Verified matches {#verified}

Only **verified** entries are shown as identifications. BioID fetches each
candidate's record again (sequence, structure or chemistry) and compares it
with your molecule. A chemical needs a skeleton-fingerprint similarity of at
least 0.7; a protein, nucleic acid or structure needs a real similarity
measurement, or an exact claim from the database search itself. Candidates
that fail are kept as **rejected candidates** with the reason.

### The matches table {#matches-table}

- **Entry** — the database and its identifier, linked to the record.
- **What it is** — the record's name (and organism, when known).
- **Match to your molecule** — what the comparison found: the sequence
  identity, *same structure* (identical chemistry), *similar skeleton (N %)*
  for a chemical analogue, *same element* for an ion, or *same structure
  (stereo not compared)* for a fold match from Foldseek or AlphaFind.
- **Confidence** — as [above](#confidence).

**Related entries** counts entries that describe the same molecule in
another database (a PDB entry and its UniProt accession).

### Rejected candidates {#rejected}

Candidates a search proposed that did not survive verification, with the
reason: sequence identity too low, structure or skeleton does not match,
different formula or element, or the record could not be checked. They are
leads for your own judgement, not identifications.

### Molecules that are not identified {#not-identified}

No database entry passed verification. Common reasons: a designed or
modified molecule that no database holds, a residue name or topology that
does not describe the molecule, a fragment too short to search, or a search
cut by its time limit (the run then says *Finished: partial*).

### Coarse-grained and bead models {#coarse-grained}

**Coarse-grained** systems (Martini and similar) model several atoms as one
bead, so BioID has no atoms to check against a database structure. Their
molecules read *Coarse-grained (Martini POPE)*: the name comes from the
residue name only and was not checked. A protein represented by beads
(coarse-grained, or Cα atoms only) is **described** in the results download
(`data.descriptions` in the JSON): its residue sequence and the best
structure and sequence search hits, as leads, never as verified
identifications.

### Sequence and chemistry {#descriptions}

What BioID searched with, read from your files. Proteins and nucleic acids
have their sequence per chain (copy or download it as FASTA). Small
molecules, lipids and glycans have a formula, SMILES and InChIKey: the bond
orders and charges are worked out from the simulated structure, implicit
hydrogens of united-atom force fields are added back, and stereochemistry is
taken from the 3D coordinates. See
[Identification & verification](identifiers.md#stage-1-signatures).

### Run progress {#run-progress}

A run goes through six steps: **Read files** (the topology and coordinates
are loaded and repaired: missing elements and bonds, molecules split by the
periodic box made whole), **Find molecules**, **Describe molecules** (the
sequences and chemistry above), **Search databases**, **Check matches**
(verification) and **Prepare downloads**. Each search step has a time limit;
when one is reached the run still finishes, marked *partial*. Messages with a
code are explained under [Warnings and errors](warnings.md).

### Technical details {#technical-details}

The *Technical details* fold below the results shows everything behind them:

- **Your files and how they were read** — the files, and each loading
  strategy tried with its outcome.
- **Molecule descriptions** — every signature generated for the molecule.
- **Database searches** — every search (*resolver*) and its raw hits:
  *Hit type* is *identity* (the search claims an exact match) or
  *similarity* (a ranked near neighbour); *Score* is the search's own 0–100
  score; BLAST hits also carry the *E-value* (lower is better), *Bit score*,
  *Identity %* and *Coverage %* of the alignment.
- **All candidates with scores** — every candidate the verification checked,
  verified or rejected, with its similarity and confidence.
- **All messages with codes** and **Logs and settings used**.

The buttons in the run header download the identifications as CSV or the
full results as JSON ([what is in the JSON](results-json.md)).

## REST API

Everything the web application does is available over HTTP. The
[REST API](rest-api.md) guide walks through submitting, polling, reading the
results, settings, limits and error codes; the [API reference](api-reference.md)
lists every endpoint with real examples, and lets you try them.

```bash
BIOID=https://bioid-ceitec.dyn.cloud.e-infra.cz/api/v1

# submit (optional: run_name, preset, config_json)
curl -F files=@topol.tpr -F files=@conf.gro -F preset=quick "$BIOID/runs"
# -> {"run_id": "…", "status": "queued", …}

# poll until pipeline.status is "success" (or "failed")
curl "$BIOID/runs/$RUN_ID/status"

# molecules and their identifications
curl "$BIOID/runs/$RUN_ID/molecules"
curl -o results.csv "$BIOID/runs/$RUN_ID/download/results.csv"
```

`GET /runs/config/options` lists the presets and the settings a run may
change, with their defaults. To change a setting, post only what differs, as
`config_json`:

```bash
curl -F files=@system.pdb -F preset=exact \
     -F 'config_json={"verification": {"min_final_confidence": 50}}' \
     "$BIOID/runs"
```

## Contact

Questions and bug reports: [tomas.pavlik@muni.cz](mailto:tomas.pavlik@muni.cz).
