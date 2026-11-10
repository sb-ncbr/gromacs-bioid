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
| GROMACS | `.tpr`, or `.top` with its `.itp` includes, plus `.gro` coordinates |
| AMBER | `.prmtop`/`.parm7` plus `.rst7`/`.inpcrd`/`.nc`/`.mdcrd` coordinates |
| CHARMM / NAMD | `.psf` plus `.pdb`/`.crd` coordinates (a `.dcd` works as the starting frame) |
| LAMMPS | a single `.data` file |
| Structures | `.pdb` / `.cif` |
| Bundles | `.zip` / `.tar` / `.tar.gz` of the above |

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
| **Balanced** (default) | Every database, exact and similar matches. | Most runs. |
| **Quick look** | Skips the slowest searches (NCBI nr/nt, UniRef50, the AlphaFind, Foldseek and RCSB structure searches) and verifies 30 candidates per molecule instead of 100. | A first look at a large system; minutes rather than up to an hour. |
| **Exact matches** | Every similarity search is off; only identical database entries are reported. | You expect known molecules and do not want homologues or analogues. |
| **Deep search** | Verifies 150 candidates per molecule (plus 60 from the supplementary databases) and keeps 20 similar matches; also searches mixed protein/nucleic-acid PDB complexes. | Unusual or engineered molecules where the best match is not obvious. Slowest. |

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

## Reading the results

The run page lists the molecules found. For each one it shows the best
identification, its database entries (with links), and a **confidence**
from 0 to 100. The confidence combines three terms: how strongly the
databases agree on the match, how closely the molecule matches the entry
(sequence identity and coverage, fingerprint similarity or structural
TM-score), and how complete the database record is. **Verified** means the
candidate was re-fetched from its database and checked against the molecule.

The buttons in the run header download the identifications as CSV or the
full results as JSON; the *Technical details* fold shows the signatures,
every database hit and the run log.

## REST API

Everything the web application does is available over HTTP. The interactive
reference (Swagger) is at
[/docs](https://bioid-ceitec.dyn.cloud.e-infra.cz/docs); the
[REST API](rest-api.md) page walks through submitting, polling, reading the
results, settings, limits and error codes.

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
