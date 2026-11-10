# REST API

Everything the web application does is available over HTTP, without an
account or API key. The base URL is

```text
https://bioid-ceitec.dyn.cloud.e-infra.cz/api/v1
```

The interactive reference (Swagger, generated from the code) is at
[/docs](https://bioid-ceitec.dyn.cloud.e-infra.cz/docs), the OpenAPI schema
at `/openapi.json`. This page explains the calls you need and how they fit
together. All paths below are relative to the base URL unless they start
with `/files`.

## A complete session

```bash
BIOID=https://bioid-ceitec.dyn.cloud.e-infra.cz/api/v1

# 1. submit (keep the answer: its owner_token is needed to cancel or delete the run)
curl -s -F files=@topol.tpr -F files=@conf.gro \
     -F run_name="lysozyme in water" -F preset=balanced \
     "$BIOID/runs" > submitted.json
RUN_ID=$(python3 -c 'import json; print(json.load(open("submitted.json"))["run_id"])')

# 2. wait: poll every minute or two
curl -s "$BIOID/runs/$RUN_ID/queue"      # {"state": "queued", "position": 3, "ahead": 2}
curl -s "$BIOID/runs/$RUN_ID/status"     # pipeline.status: queued → running → success / failed / cancelled

# 3. results
curl -s "$BIOID/runs/$RUN_ID/molecules"
curl -s "$BIOID/runs/$RUN_ID/verification"
curl -o results.csv  "$BIOID/runs/$RUN_ID/download/results.csv"
curl -o results.json "$BIOID/runs/$RUN_ID/download/results.json"
```

## Submitting a run

`POST /runs` — `multipart/form-data`:

| Field | Required | Meaning |
|---|---|---|
| `files` | yes, repeat for each file | the simulation files (formats in [Submitting a simulation](index.md#submitting-a-simulation)); a `.zip` / `.tar` / `.tar.gz` bundle also works; at most 50 files |
| `run_name` | no | a label shown in the run list and the results page |
| `preset` | no | `balanced` (the default settings), `quick`, `exact` or `deep`; see [Presets](index.md#presets-and-advanced-configuration) |
| `config_json` | no | settings to change, as JSON `{"section": {"field": value}}`; applied after the preset |
| `retention` | no | how long the results are kept: omit for the default 30 days, a number of days (1–365), or `preserve` to keep them indefinitely |
| `config_file` | no | the same as an uploaded `config.ini` (instead of `config_json`); only the fields that differ from the server's settings count |

The response comes at once; the run is queued:

```json
{"run_id": "1c2a4d4b-…", "status": "queued",
 "message": "Run 1c2a4d4b-… queued successfully",
 "results_url": "/runs/1c2a4d4b-…/status",
 "owner_token": "q3J…"}
```

`owner_token` is shown only here. Keep it: cancelling or deleting the run
needs it, sent as the `X-Owner-Token` header. (The web application keeps it
in your browser.)

The results page in the web application is
`https://bioid-ceitec.dyn.cloud.e-infra.cz/runs/<run_id>`.

### Changing settings

`GET /runs/config/options` returns two things:

- `config`: every setting a run may change, grouped by section
  (`identifiers`, `verification`, `blast`, `chembl`, `idsm`, `pubchem`,
  `pdb`, `signatures`, `loader`), with the server's current values;
- `presets`: the four presets, each with its `overrides`.

The server applies its own settings, then the preset, then your
`config_json`. Post only what you want to change:

```bash
# exact matches only, and mark a hit verified only from confidence 50
curl -F files=@system.pdb -F preset=exact \
     -F 'config_json={"verification": {"min_final_confidence": 50}}' \
     "$BIOID/runs"

# skip the NCBI nr search, keep everything else
curl -F files=@system.pdb \
     -F 'config_json={"identifiers": {"blast_nr_protein": false, "blast_nr_protein_similarity": false}}' \
     "$BIOID/runs"
```

Database switches are listed with what each one searches on the
[Databases](databases.md) page. Settings that belong to the deployment
(database paths, programs, service addresses, timeouts, parallelism) cannot
be changed; a request that changes one is rejected with 422 before anything
is queued. Repeating a server value unchanged is accepted, so posting back
the whole `config` object works. Booleans must be JSON `true`/`false`;
numbers are checked against their allowed range (for example
`verify_top_n` 1–200, `min_final_confidence` 0–100). The preset used is
recorded as `pipeline.preset` in results.json.

## Following a run

| Call | Returns |
|---|---|
| `GET /runs/{id}/queue` | `state` (`queued`, `running`, `done`), and while queued, `position` and `ahead` (runs before yours) |
| `GET /runs/{id}/status` | `pipeline` (with `status`), per-stage `tasks`, `warnings`, `critical_errors`, `events`, and `progress` (`molecules_done` / `molecules_total` during identification). `?since=<ISO 8601>` returns only newer warnings, errors and events |
| `GET /runs/{id}` | a short summary: status, times, input kind, run name, counts of tasks, warnings and errors |
| `GET /runs/{id}/loading` | how the input files were read: strategy, attempts, topology files, why a load failed |
| `GET /runs/{id}/logs` | the run log as text (`?type=debug` for the verbose log) |
| `POST /runs/{id}/cancel` | cancels a queued or running run; needs `X-Owner-Token` (403 without it, 400 if the run already finished) |

`pipeline.status` ends as `success`, `failed` or `cancelled`. A finished run
can still carry warnings, for example a database search that timed out; the
molecules affected may then miss matches from that database.

Typical run time: a few minutes for a small structure, up to about an hour
for a large system with every database searched. `GET /capabilities` reports
the deployment's typical duration and code version.

## Reading the results

| Call | Returns |
|---|---|
| `GET /runs/{id}/molecules` | the distinct molecules (`segments`), their type counts and per-molecule metadata (`segment_meta`: display name, number of copies, chains) |
| `GET /runs/{id}/molecules/{segment}/info` | one molecule: name, type, atom and residue counts, confidence of its best hit |
| `GET /runs/{id}/verification` | the ranked, verified hit table per molecule: identifier, database and link, name, organism, `final_confidence` (0–100) and its terms, `is_verified`, `rejection_reason`. `?segment=<name>` for one molecule |
| `GET /runs/{id}/identifiers` | every raw database hit before verification, with BLAST e-value, identity and coverage where they apply, plus the searches attempted and failed. `?segment=` |
| `GET /runs/{id}/signatures` | the molecule descriptions BioID generated (sequences, SMILES, InChIKey, formulas, structures …). `?segment=` |
| `GET /runs/{id}/download/results.csv` | one row per molecule: best verified hit, confidence label, up to three alternatives |
| `GET /runs/{id}/render` | paths of the whole-system mmCIF and PNG renders, and per-molecule selectors |
| `GET /runs/{id}/files` | every file of the run directory |
| `GET /runs/{id}/download/results.json` | the complete record of the run, without the submitter's address; structure in the [results.json reference](results-json.md) |
| `GET /files/{id}/results.json` | the same file as stored (no `/api/v1` prefix) |
| `GET /files/{id}/<path>` | any file listed by `/runs/{id}/files`, e.g. `results.log` or the system mmCIF |
| `GET /runs/{id}/download/topology-less-pdb`, `.../ca-only-pdb` | a molecule's structure signature as PDB (`?segment=` when there are several) |

How to read the confidence and the verified flag is explained in
[Reading the results](index.md#reading-the-results); the scoring itself in
[Identification & verification](identifiers.md).

## Other calls

| Call | Returns |
|---|---|
| `GET /runs/examples` | the finished example runs shown on the front page (`?limit=`) |
| `GET /runs` | the runs submitted from your network address (what *Your annotations* shows); other people's runs are never listed |
| `POST /runs/{id}/rerun` | a new run with the same input files and settings; returns the new `run_id` and its `owner_token` |
| `DELETE /runs/{id}` | deletes the run and its files; needs `X-Owner-Token` |

```bash
curl -X POST   -H "X-Owner-Token: $TOKEN" "$BIOID/runs/$RUN_ID/cancel"
curl -X DELETE -H "X-Owner-Token: $TOKEN" "$BIOID/runs/$RUN_ID"
```

Runs submitted before 10 November 2026 and the example runs have no owner
token and cannot be cancelled or deleted through the API.
| `GET /capabilities` | API feature markers, typical run duration, deployed code version |
| `GET /health` | service health |

## Limits and errors

- **Upload size**: at most 128 MiB per file, and the whole request is also
  limited to 128 MiB by the web server; larger requests fail with 413.
- **Files**: at most 50 per run; only simulation, structure, configuration
  and archive files (the formats above) are accepted.
- **Submissions**: at most 30 runs (new or re-runs) per hour from one network
  address, and none while 40 runs are already waiting in the queue. Both
  answer **429** with a `Retry-After` header (seconds) and a message saying
  when to try again. Poll no more than about once a minute; for large
  batches, write to the contact below first.
- **Retention**: a finished run is deleted 30 days after it finished, unless
  it was submitted with another `retention` (days, or `preserve`). Runs
  submitted before 10 November 2026 are kept until at least 10 December 2026.
  The example runs are never deleted.

| Status | When |
|---|---|
| 404 | unknown run id, or a molecule (`segment`) that is not in the run |
| 413 | a file (or the request) is larger than 128 MiB, or more than 50 files |
| 422 | no usable file names, duplicate file names, a file type BioID does not read, invalid `config_json`, an unknown preset, an unknown or non-changeable setting, a value of the wrong type or out of range, a malformed run id |
| 429 | too many submissions from your address this hour, or the queue is full; see `Retry-After` |
| 403 | cancelling or deleting without the run's owner token; deleting an example run |
| 409 | `run_id` given for a run that already exists |
| 400 | cancelling a run that already finished; a PDB download without `segment` when the run has several molecules |
| 500 | a server-side failure; please report it |

Error responses are JSON: `{"detail": "<message>"}`.

## Privacy

Runs are not tied to an account: **anyone who has a run's id can open its
results and re-run it**; only the holder of its owner token can cancel or
delete it. Run ids are random and are not listed to others. The service keeps
a keyed hash of the address a run was submitted from (to list *Your
annotations* and apply the limits), not the address itself.

For usage statistics the service records each page view of the web
application and the documentation, and each meaningful API call
(submissions, results, downloads, errors), with the time, the page or
endpoint, the kind of client, the referring site, the same keyed address
hash and an approximate location (city, coordinates rounded to about 10 km)
looked up from the address at that moment. The address is never stored.
Raw records are kept 90 days. Browsers sending *Do Not Track* or *Global
Privacy Control* are not counted. IP geolocation by
[DB-IP](https://db-ip.com) (CC BY 4.0). Sequences and
structures of your molecules are sent to public search services (for
example RCSB PDB, PubChem, AlphaFind) to find matches. Do not submit data you
are not allowed to share.

Questions and bug reports: [tomas.pavlik@muni.cz](mailto:tomas.pavlik@muni.cz).
