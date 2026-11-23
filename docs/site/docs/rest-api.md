# REST API

Everything the web application does is available over HTTP, without an
account or API key:

```text
https://bioid-ceitec.dyn.cloud.e-infra.cz/api/v1
```

This page explains how a session goes and what the answers mean, with real
answers of the server for the trypsin example run (PDB 3PTB: trypsin, its
inhibitor benzamidine, a calcium ion and crystal water; run id
`1c2a4d4b-94cb-48ec-81a9-d0c0924af8bd`, kept permanently, so every call
below works as written). Every endpoint, parameter and error is in the
**[API reference](api-reference.md)**, where you can also try the calls.

## Quick start

```bash
BIOID=https://bioid-ceitec.dyn.cloud.e-infra.cz/api/v1

# 1. submit: keep the answer, its owner_token is shown only once
curl -s -F files=@topol.tpr -F files=@conf.gro -F run_name="lysozyme in water" \
     "$BIOID/runs" > submitted.json
RUN_ID=$(python3 -c 'import json; print(json.load(open("submitted.json"))["run_id"])')

# 2. wait: poll about once a minute until pipeline.status is success, failed or cancelled
curl -s "$BIOID/runs/$RUN_ID/status"

# 3. read the results
curl -s "$BIOID/runs/$RUN_ID/molecules"
curl -s "$BIOID/runs/$RUN_ID/verification"
curl -s -O -J "$BIOID/runs/$RUN_ID/download/results.csv"
```

The same in Python, with the 429 answer (too many submissions, queue full)
handled:

```python
import time
import requests

BIOID = "https://bioid-ceitec.dyn.cloud.e-infra.cz/api/v1"

def submit(paths, **form):
    while True:
        files = [("files", open(p, "rb")) for p in paths]
        r = requests.post(f"{BIOID}/runs", files=files, data=form, timeout=600)
        if r.status_code != 429:
            r.raise_for_status()          # 413/422: the message in r.json()["detail"] says why
            return r.json()               # run_id, owner_token, ...
        time.sleep(int(r.headers.get("Retry-After", "600")))

def wait(run_id):
    while True:
        status = requests.get(f"{BIOID}/runs/{run_id}/status", timeout=60).json()
        if status["pipeline"]["status"] in ("success", "failed", "cancelled"):
            return status
        time.sleep(60)

run = submit(["topol.tpr", "conf.gro"], run_name="lysozyme in water")
status = wait(run["run_id"])
hits = requests.get(f"{BIOID}/runs/{run['run_id']}/verification", timeout=60).json()["hits"]
best = {}
for h in hits:                            # best verified identification per molecule
    if h["is_verified"] and (h["segment"] not in best
                             or (h["final_confidence"] or 0) > (best[h["segment"]]["final_confidence"] or 0)):
        best[h["segment"]] = h
for segment, h in best.items():
    print(segment, h["database"], h["identifier"], h["name"], h["final_confidence"])
```

## Submitting

`POST /runs` takes `multipart/form-data`: the simulation files as `files`
(repeat the field), and optionally `run_name`, `preset`, `config_json` and
`retention`.

| Package | Files |
|---|---|
| GROMACS | `.tpr` (+ `.gro`/`.xtc`), or `.gro` + `.top` (+ `.itp`) |
| AMBER | `.prmtop`/`.parm7` + `.inpcrd`/`.rst7`/`.nc` |
| CHARMM / NAMD | `.psf` + `.pdb`/`.crd`/`.dcd` |
| LAMMPS | `.data` |
| Structures | a single `.pdb`, `.cif`/`.mmcif` or `.gro` |

A `.zip`, `.tar`, `.tar.gz` or `.tgz` is unpacked (folders are flattened, so
file names must be unique). Files that do not make a complete simulation are
refused at once with 422 and a message listing what would; a `.gro` without
a topology is accepted with a note that identification will likely be
incomplete.

The answer comes at once:

```json
{"run_id": "7b0e5f2c-3d41-4a8e-9f61-2c8d0a4b5e17",
 "status": "queued",
 "message": "Run 7b0e5f2c-3d41-4a8e-9f61-2c8d0a4b5e17 queued successfully",
 "results_url": "/api/v1/runs/7b0e5f2c-3d41-4a8e-9f61-2c8d0a4b5e17/status",
 "owner_token": "q3J9xVb2mT0kZr7LwP4sNd8eYh6uCa1F"}
```

**Keep the `owner_token`.** It is shown only here; cancelling, deleting and
keeping the run longer need it, sent as the `X-Owner-Token` header. (The web
application keeps it in your browser.) The results page in the web
application is `https://bioid-ceitec.dyn.cloud.e-infra.cz/runs/<run_id>`.

### Presets and settings

The server starts from its own settings, the `preset` pre-fills changes, and
your `config_json` overrides both:

| Preset | What it does |
|---|---|
| `balanced` | the server's settings (the default) |
| `quick` | skips the slow structure searches (RCSB, AlphaFind, Foldseek) and NCBI; verifies fewer candidates |
| `exact` | exact matches only: no similarity searches |
| `deep` | adds NCBI nr, nt and core_nt and verifies more candidates; hours per protein |

`GET /runs/config/options` lists every setting a run may change, with the
server's values, and the presets with their overrides. Post only what you
change:

```bash
# exact matches only, and mark a hit verified only from confidence 50
curl -F files=@system.pdb -F preset=exact \
     -F 'config_json={"verification": {"min_final_confidence": 50}}' "$BIOID/runs"

# the balanced settings plus NCBI nr for proteins (hours per protein)
curl -F files=@system.pdb \
     -F 'config_json={"identifiers": {"blast_nr_protein": true, "blast_nr_protein_similarity": true}}' \
     "$BIOID/runs"
```

What each database switch searches is on the [Databases](databases.md) page.
Settings that belong to the deployment (database paths, programs, service
addresses, timeouts) cannot be changed: 422; repeating their server value is
accepted, so posting back the whole `config` object works.

The preset only pre-fills the settings: **`config_json` has the last word**.
`preset=quick` with `{"identifiers": {"blast_uniref50": true}}` is the quick
preset with UniRef50 searched after all.

## Following a run

Poll `GET /runs/{id}/status` about once a minute (`GET /runs/{id}/queue` is
cheaper while the run waits: `{"state": "queued", "position": 3, "ahead": 2}`).
The trypsin run, shortened:

```json
{"run_id": "1c2a4d4b-94cb-48ec-81a9-d0c0924af8bd",
 "pipeline": {"status": "success", "started_at": "2026-11-08T23:50:46.759861+00:00",
              "finished_at": "2026-11-08T23:58:37.460787+00:00", "input_kind": "pdb",
              "completeness": "complete", "partial_stages": []},
 "tasks": [{"task_id": "discover_input", "name": "Discover Input", "status": "success", "...": "…"}],
 "progress": {"molecules_done": 4, "molecules_total": 4,
              "per_segment": {"A": "searched", "A__v1": "searched", "A__v2": "searched", "A__v3": "searched"}},
 "warnings": [{"code": "pbc_unwrap_applied",
               "message": "Periodic boundary unwrapping was applied to make molecules whole.",
               "step_id": "unwrap_periodic_boundaries", "details": {},
               "recorded_at": "2026-11-08T23:50:47.044822+00:00",
               "docs_url": "/documentation/warnings/#pbc_unwrap_applied"}],
 "critical_errors": [],
 "incomplete": [],
 "retention": {"policy": "preserve", "days": null, "expires_at": null, "example": true, "owner_choices": []},
 "queue": "web", "retry": null, "attempts": [], "restarts": [], "rerun_of": null, "superseded_by": null}
```

- `pipeline.status` goes `queued` → `running` → `success`, `failed` or
  `cancelled`. Typical runs take 2–8 minutes; Deep search up to hours.
- `pipeline.completeness` says how complete a successful run is (null
  before): `complete`; `partial`, a stage ran out of its time limit
  (`partial_stages`, e.g. `["identify_molecules"]`) and molecules handled
  after the limit may have fewer matches or none; or `incomplete`, database
  lookups failed (listed in `incomplete`, below). **`status` stays `success`
  in all three**, so a client that stores results should check
  `completeness` as well. The run summary (`GET /runs/{id}`) and the run list
  (`GET /runs`) carry the same two fields next to `status`.
- `warnings` do not mean the run failed: each has a `code`, `details` (often
  the molecule, `segment`, and the database, `service`) and a `docs_url` into
  [Warnings and errors](warnings.md). A database that did not answer, for
  example, means the molecules concerned may lack its matches.
- `?since=2026-11-08T23:55:00Z` returns only the warnings, errors and events
  recorded from then on (no zone means UTC; write `+` as `%2B`).

### Incomplete runs and reruns

`incomplete` lists lookups that failed for a reason another attempt can fix:
a database answered with a server error, was busy or unreachable, or did not
answer in time. `POST /runs/{id}/rerun` repeats the run; lookups that worked
come from the cache, so in practice only the failed ones are repeated. The
answer is a new run with its own `owner_token`. Sent with the old run's
`X-Owner-Token`, the old run is marked `superseded_by` the new one; a body
`{"preset": "deep"}` reruns the files with that preset instead of the old
choices.

On the `repository` queue (campaigns, with a queue token from the BioID
team), failed lookups can be retried automatically under the same run id:
while a run waits for its next attempt, `status` reads `queued` and `retry`
says when (`at`) and why. A run whose only gaps are time limits
(`completeness: partial`, `incomplete` listing only `time limit (…)`) is not
retried automatically: under the same limit it would most likely run out of
time again.

A run whose processing server restarts (an update, a scale-down) is queued
again at once under the same run id and starts over: `status` goes back to
`queued`, then `running`, `restarts` lists each such restart and an event of
kind `worker_restart` says so. Nothing needs to be resubmitted, and it is not
counted as an attempt. On the `repository` queue a server that stopped
without warning (out of memory, a lost machine) is noticed within a few
minutes and the run is retried at once as its next attempt (`attempts`,
reason `worker_lost`).

## Reading the results

**`GET /runs/{id}/molecules`** says what the system is made of. Every other
call addresses a molecule by its `segment` name:

```json
{"segments": ["A", "A__v1", "A__v2", "A__v3"],
 "type_counts": {"protein": 1, "small_molecule": 1, "ion": 1, "water": 1},
 "segment_meta": {
   "A":     {"type": "protein",        "atom_count": 1629, "residue_count": 223, "copies": 1,  "display_name": "A"},
   "A__v1": {"type": "small_molecule", "atom_count": 9,    "residue_count": 1,   "copies": 1,  "display_name": "BEN"},
   "A__v2": {"type": "ion",            "atom_count": 1,    "residue_count": 1,   "copies": 1,  "display_name": "CA"},
   "A__v3": {"type": "water",          "atom_count": 1,    "residue_count": 1,   "copies": 62, "display_name": "HOH"}}}
```

Identical molecules are one entry with `copies` (the 62 waters). A molecule
of a coarse-grained model also carries `"coarse_grained": {"model": "Martini",
"residue": "POPE", "by_name": "PE(16:0/18:1(9Z))"}` (see
[results.json](results-json.md#datafragments)).

**`GET /runs/{id}/verification`** is the main result: for each molecule the
database records BioID found, verified ones first. `?segment=A__v1`, the
benzamidine:

```json
{"segment": "A__v1",
 "hits": [{"identifier": "PXXJHWLDUBFPOL-UHFFFAOYSA-N", "ident_type": "INCHIKEY", "database": "pubchem",
           "name": "Benzamidine", "final_confidence": 80.0, "is_verified": true,
           "resolver_score": 100.0, "similarity_score": null, "annotation_quality_score": 100.0,
           "database_url": "https://pubchem.ncbi.nlm.nih.gov/#query=PXXJHWLDUBFPOL-UHFFFAOYSA-N",
           "segment": "A__v1", "rejection_reason": null, "...": "…"},
          {"identifier": "17943838", "database": "pubchem", "name": "1,1-Diaminomethylcyclohexane",
           "final_confidence": 77.55555555555556, "is_verified": true, "...": "…"}]}
```

- `final_confidence` (0–100) is how sure BioID is that the record is this
  molecule: **≥ 80 high, ≥ 50 medium**, below that a lead to check. The best
  identification of a molecule is its verified hit with the highest
  `final_confidence`; that is what the results page and results.csv show.
- Unverified hits (`is_verified: false`) say why in `rejection_reason`.
- Ions and water are identified exactly (`ground_truth_override` set) and have
  no confidence to weigh.
- How the scores are computed: [Identification & verification](identifiers.md);
  how to read them: [Reading the results](index.md#reading-the-results).

**`GET /runs/{id}/download/results.csv`** gives one row per molecule:

```text
Segment,Display Name,Kind,Copies,Atoms,Result,Identified Name,Best Database,Best Identifier,Database URL,Confidence,Confidence Label,Alternatives
A,A,protein,1,1629,identified,Serine protease 1,UniProt,P00760,https://www.uniprot.org/uniprotkb/P00760,84.1,high,PDB:1AQ7 PDB:1AUJ PDB:1AZ8
A__v1,BEN,small_molecule,1,9,identified,Benzamidine,PubChem,PXXJHWLDUBFPOL-UHFFFAOYSA-N,https://pubchem.ncbi.nlm.nih.gov/#query=PXXJHWLDUBFPOL-UHFFFAOYSA-N,80.0,high,PubChem:OYOFUEDXAMRQBB-UHFFFAOYSA-N PubChem:17943838 PubChem:68458528
A__v2,CA,ion,1,1,exact,Calcium ion,Element,CA,,,,
A__v3,HOH,water,62,1,exact,Water,PubChem,962,https://pubchem.ncbi.nlm.nih.gov/compound/962,,,
```

`Result` is `identified`, `lead` (verified, confidence below 50), `exact`,
`not identified` or `coarse-grained` (a bead model with nothing verified: it
has no atoms to check against a database; `Identified Name` reads e.g.
`Coarse-grained (Martini POPE)`).

Going deeper:

| Call | What it gives |
|---|---|
| `GET /runs/{id}/identifiers?segment=A` | every raw database hit before verification: which search found it, BLAST e-value, identity and coverage |
| `GET /runs/{id}/signatures?segment=A__v1` | what BioID searched with: sequences, SMILES, InChIKey, formula, structures |
| `GET /runs/{id}/download/results.json` | the complete record, described in the [results.json reference](results-json.md) |
| `GET /runs/{id}/files`, then `/files/{id}/<path>` | structures (`system.mmcif`, `<segment>.mmcif`), pictures (`render/system.png`), logs, inputs. Note: `/files` has no `/api/v1` prefix |
| `GET /runs/{id}/render` | the same structures and pictures by molecule, and where each molecule is in `system.mmcif` |
| `POST /runs/{id}/reports` | tell the BioID team an identification looks wrong: `{"segment": "A__v1", "note": "…", "suggestion": "…"}` |

## Managing runs

| Call | Needs the owner token | What it does |
|---|---|---|
| `POST /runs/{id}/cancel` | yes | stops a queued or running run |
| `POST /runs/{id}/retention` `{"days": 90}` | yes | keeps a finished run 30, 90, 180 or 365 days from now (only extends) |
| `DELETE /runs/{id}` | yes | deletes the run and its files (cancel a running run first) |
| `POST /runs/{id}/rerun` | no (optional) | a new run with the same files and settings |
| `GET /runs` | no | the runs submitted from your network address, newest first |

```bash
curl -X POST   -H "X-Owner-Token: $TOKEN" "$BIOID/runs/$RUN_ID/cancel"
curl -X DELETE -H "X-Owner-Token: $TOKEN" "$BIOID/runs/$RUN_ID"
```

Finished runs are deleted 30 days after they finish unless submitted with
another `retention` (1–365 days, or `preserve`) or kept longer. Example runs
and runs submitted before 10 November 2026 have no owner token.

## Limits and errors

- **Uploads**: at most 128 MiB per file and per request (larger requests get
  the web server's 413 page), 50 files per run; archives at most 500 files,
  128 MiB each and 2 GiB unpacked.
- **Submissions** (new runs and reruns): 30 per hour from one network
  address, and none while 40 runs wait to start. Both answer **429** with a
  `Retry-After` header (seconds). For large batches, write to us first.
- **Reports**: 20 per hour from one address.
- **Polling**: about once a minute is plenty.

Errors are JSON `{"detail": "<message>"}`; the message says what to change.
(Parameters of the wrong type give 422 with `detail` as a list.)

| Status | When |
|---|---|
| 400 | cancelling a finished run; `days` not 30/90/180/365; a PDB download without `segment` when the run has several molecules |
| 403 | cancelling, deleting or keeping longer without the run's owner token; deleting an example run; the repository queue without a queue token |
| 404 | unknown run id or molecule; a rerun of a run whose input files are gone |
| 409 | deleting a queued or running run; keeping longer a run that has not finished or is already kept longer |
| 413 | more than 50 files, or a file or request over 128 MiB |
| 422 | files that do not make a simulation, an unreadable archive, an unknown preset, an unknown or non-changeable setting or a value out of range |
| 429 | too many submissions or reports from your address, or the queue is full; see `Retry-After` |
| 500 | a failure on our side: please report it |

## Privacy

Runs are not tied to an account: **anyone who has a run's id can open its
results and rerun it**; only the holder of its owner token can cancel,
delete or keep it longer. Run ids are random and are not listed to others.
The service keeps a keyed hash of the address a run was submitted from (to
list *Your annotations* and apply the limits), not the address itself.

For usage statistics the service records each page view of the web
application and the documentation, and each meaningful API call
(submissions, results, downloads, errors), with the time, the page or
endpoint, the kind of client, the referring site, the same keyed address
hash and an approximate location (city, coordinates rounded to about 10 km)
looked up from the address at that moment. The address is never stored.
Raw records are kept 90 days. Page views from browsers sending *Do Not
Track* or *Global Privacy Control* are not counted. IP geolocation by
[DB-IP](https://db-ip.com) (CC BY 4.0). Sequences and structures of your
molecules are sent to public search services (for example RCSB PDB,
PubChem, AlphaFind) to find matches. Do not submit data you are not allowed
to share.

Questions and bug reports: [tomas.pavlik@muni.cz](mailto:tomas.pavlik@muni.cz).
