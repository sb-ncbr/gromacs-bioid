"""The published API reference: /docs (Swagger) and /openapi.json (2026-11-19).

Only the public /api/v1 routes are published (the BioID host routes /api,
/files and /health here; the root-level router duplicates and UI helpers
stay callable in-cluster; the campaign control plane is gone, GitHub #29).
Each published route gets
from ENDPOINTS below a user-facing summary and description, descriptions of
its parameters, the errors it answers with, and a response example: a real
answer of this server for the trypsin example run, captured by
scripts/capture_api_examples.py into openapi_examples.json.

tests/src_new/test_openapi_docs.py checks that every published route is
covered and that the examples still match the response models.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

EXAMPLES_FILE = Path(__file__).with_name("openapi_examples.json")


def examples() -> dict[str, Any]:
    return json.loads(EXAMPLES_FILE.read_text())


@dataclass
class Endpoint:
    tag: str
    summary: str
    description: str
    #: key in openapi_examples.json, or a literal example (dict / str)
    example: Any = None
    #: media type of the 200 answer when it is not JSON
    media: Optional[str] = None
    #: status -> (when, example detail message)
    errors: dict[int, tuple[str, str]] = field(default_factory=dict)
    #: parameter name -> description (path, query, header)
    params: dict[str, str] = field(default_factory=dict)
    #: description of the 200 answer
    returns: str = "Successful answer"
    #: further named examples of the 200 answer: name -> (summary, key or literal)
    more_examples: dict[str, tuple[str, Any]] = field(default_factory=dict)
    #: request body example (JSON bodies)
    body_example: Any = None


#: the trypsin example run: kept permanently, so "Try it out" always answers
EXAMPLE_RUN = "1c2a4d4b-94cb-48ec-81a9-d0c0924af8bd"
#: example values of parameters that many routes share ("Try it out" fills them in)
PARAM_EXAMPLES = {"run_id": EXAMPLE_RUN, "segment": "A__v1"}

DOCS = "/documentation"

API_DESCRIPTION = f"""
BioID identifies the molecules in a molecular dynamics simulation: proteins,
nucleic acids, ligands, lipids, glycans, ions and solvent. You upload the
simulation files; BioID splits the system into molecules, describes each one
(sequence, SMILES, InChIKey, formula, structure), searches public databases
(PDB, UniProt, PubChem, ChEMBL, ChEBI, LIPID MAPS, AlphaFold DB, NCBI …) and
verifies the candidates. Every call the web application makes is available
here, without an account or API key.

**Base URL:** `https://bioid-ceitec.dyn.cloud.e-infra.cz/api/v1`

**Try it out:** every endpoint below is pre-filled with the trypsin example
run (`{EXAMPLE_RUN}`, PDB 3PTB: trypsin, benzamidine, a calcium ion and
crystal water), and every response example is that run's real answer,
shortened where lists are long.

### A session in four calls

```bash
BIOID=https://bioid-ceitec.dyn.cloud.e-infra.cz/api/v1
curl -F files=@topol.tpr -F files=@conf.gro -F run_name="lysozyme in water" "$BIOID/runs"
#   -> {{"run_id": "…", "owner_token": "…", "status": "queued", …}}   keep the owner_token
curl "$BIOID/runs/$RUN_ID/status"            # poll about once a minute until pipeline.status is
                                             # success, failed or cancelled
curl "$BIOID/runs/$RUN_ID/verification"      # the identifications, with confidence
curl -O -J "$BIOID/runs/$RUN_ID/download/results.csv"   # one row per molecule
```

### Conventions

* **Molecules** are addressed by their `segment` name (`A`, `A__v1`, `PROA`, …),
  as listed by `GET /runs/{{run_id}}/molecules`.
* **Errors** are JSON `{{"detail": "<message>"}}`; the message says what to change.
  Parameters of the wrong type give 422 with `detail` as a list of problems.
* **Owner token**: `POST /runs` returns it once. Cancelling, deleting and keeping
  a run longer need it in the `X-Owner-Token` header. Anyone with a run's id can
  read its results.
* **Limits**: 128 MiB per file and per request, 50 files per run, 30 submissions
  per hour per network address, and no new runs while 40 are waiting (429 with
  `Retry-After`). Poll no more than about once a minute.
* Times are ISO 8601 in UTC.

### More

[REST API guide]({DOCS}/rest-api/) ·
[results.json reference]({DOCS}/results-json/) ·
[Warnings and errors]({DOCS}/warnings/) ·
[Databases]({DOCS}/databases/) ·
[MCP server for AI assistants]({DOCS}/mcp/) ·
OpenAPI document: [/openapi.json](/openapi.json) ·
Contact: [tomas.pavlik@muni.cz](mailto:tomas.pavlik@muni.cz)
"""

TAGS: list[dict[str, str]] = [
    {"name": "Runs", "description":
        "Submit simulation files and follow the run through the queue and the pipeline. "
        "A run goes `queued` → `running` → `success`, `failed` or `cancelled`; typical runs "
        "take 2–8 minutes, Deep search (NCBI nr/nt) up to hours."},
    {"name": "Settings", "description":
        "Presets and the settings a run may change, with the server's values."},
    {"name": "Results", "description":
        "What a finished run found. Start with **molecules** (what is in the system) and "
        "**identifications** (the database record of each molecule, with confidence); "
        "**database hits** and **signatures** show the raw hits and the queries behind them. "
        "The complete record is **results.json** "
        f"([reference]({DOCS}/results-json/)). Results of an unfinished run are empty."},
    {"name": "Files", "description":
        "Structures, pictures, logs and the uploaded inputs of a run, as files."},
    {"name": "Managing runs", "description":
        "Your runs, and cancelling, rerunning, keeping longer and deleting a run. "
        "Cancelling, deleting and keeping longer need the run's owner token."},
    {"name": "Service", "description":
        "Example runs to try the API on, and the health and features of this deployment."},
]

V1 = "/api/v1/runs"
RUN_404 = (404, ("No run with this id", f"Run '{EXAMPLE_RUN[:8]}…' not found"))
NO_OWNER = ("Missing or wrong X-Owner-Token, or a run without an owner token (examples, "
            "runs before 10 November 2026)",
            "Only the submitter of this run can have it {action}. Send the owner token "
            "returned at submission in the X-Owner-Token header.")
OWNER_TOKEN = ("The owner token `POST /runs` returned for this run "
               "(`owner_token`); only its submitter has it.")
SEGMENT_FILTER = ("Only this molecule (a `segment` from "
                  "`/molecules`). Omit it for every molecule.")
CREATED = {"run_id": "7b0e5f2c-3d41-4a8e-9f61-2c8d0a4b5e17", "status": "queued",
           "message": "Run 7b0e5f2c-3d41-4a8e-9f61-2c8d0a4b5e17 queued successfully",
           "results_url": "/api/v1/runs/7b0e5f2c-3d41-4a8e-9f61-2c8d0a4b5e17/status",
           "owner_token": "q3J9xVb2mT0kZr7LwP4sNd8eYh6uCa1F"}
RATE_429 = (429, ("Too many submissions from your network address this hour, or the queue is "
                  "full. The `Retry-After` header says how many seconds to wait.",
                  "Too many runs from your network address: at most 30 per hour. "
                  "Please try again in 17 minutes."))

# 2026-11-21 (mdval audit item 7): status success, but not every molecule searched
PARTIAL_SUMMARY = {
    "run_id": "5d8f0a3e-6b2c-4e71-a9d4-0f3c2b7e8a19", "pipeline_name": "BAT3", "status": "success",
    "started_at": "2026-11-20T08:12:03.512144+00:00", "finished_at": "2026-11-20T09:44:51.907310+00:00",
    "input_kind": "gromacs_tpr", "run_name": "membrane patch", "task_count": 10, "warning_count": 3,
    "error_count": 0, "retention": {"policy": "default", "days": 30,
                                    "expires_at": "2026-12-20T09:44:51.907310+00:00",
                                    "example": False, "owner_choices": [30, 90, 180, 365]},
    "incomplete_count": 1, "completeness": "partial", "partial_stages": ["identify_molecules"],
    "queue": "repository", "attempt": 1, "rerun_of": None, "superseded_by": None}


def _owner(action: str) -> tuple[int, tuple[str, str]]:
    return 403, (NO_OWNER[0], NO_OWNER[1].format(action=action))


ENDPOINTS: dict[tuple[str, str], Endpoint] = {
    # ---------------------------------------------------------------- Runs
    ("POST", V1): Endpoint(
        "Runs", "Submit a run",
        f"""
Uploads the simulation files and queues a run. The answer comes at once; the
run is processed in the background (follow it with `/status`).

**Files** (`files`, repeat the field for each file): a topology together with
coordinates, for example

| Package | Files |
|---|---|
| GROMACS | `.tpr` (+ `.gro`/`.xtc`), or `.gro` + `.top` (+ `.itp`) |
| AMBER | `.prmtop`/`.parm7` + `.inpcrd`/`.rst7`/`.nc` |
| CHARMM / NAMD | `.psf` + `.pdb`/`.crd`/`.dcd` |
| LAMMPS | `.data` |
| Structures | a single `.pdb`, `.cif`/`.mmcif` or `.gro` |

A `.zip`, `.tar`, `.tar.gz` or `.tgz` is unpacked (folders flattened, so file
names must be unique; at most 500 files, 128 MiB each, 2 GiB in all). At most
50 uploaded files, 128 MiB per request. A `.gro` without a topology is
accepted with a note in `message`: identification will likely be incomplete.

**Settings**: the server's settings, then `preset`, then `config_json`, e.g.
`{{"verification": {{"min_final_confidence": 50}}}}` or
`{{"identifiers": {{"blast_nr_protein": true}}}}` (NCBI nr, off by default). Post
only what you change; the settings and their ranges are listed by
`GET /runs/config/options`. The preset only pre-fills: `config_json` has the
last word, so `preset=quick` with `{{"identifiers": {{"blast_uniref50": true}}}}`
searches UniRef50. Deployment settings (database paths, programs, timeouts)
cannot be changed: 422.

**Keep the `owner_token`**: it is shown only in this answer and is needed to
cancel, delete or keep the run longer.

```bash
curl -F files=@3PTB.pdb -F run_name="trypsin" -F preset=quick \\
     https://bioid-ceitec.dyn.cloud.e-infra.cz/api/v1/runs
```""",
        example=CREATED,
        returns="The run is queued",
        params={"X-Queue-Token": "Only for `queue=repository` (campaigns); issued by the BioID team.",
                "run_id": "Choose the run id yourself instead of a random one "
                          "(letters, digits, `.`, `_`, `-`; up to 128 characters). Rarely needed."},
        errors={
            403: ("`queue=repository` without a valid `X-Queue-Token`",
                  "The repository queue needs a valid X-Queue-Token header."),
            409: ("The `run_id` asked for exists already", "Run 'my-run-1' already exists"),
            413: ("More than 50 files, or a file or the whole request is larger than 128 MiB "
                  "(the web server then answers with an HTML page)",
                  "Too many files (51): at most 50 per run; bundle them as a .zip or .tar.gz."),
            422: ("The files do not make a complete simulation (the message lists what would), "
                  "a file type BioID does not read, duplicate names, an archive that cannot be "
                  "unpacked, an unknown preset or queue, or a setting that is unknown, not "
                  "changeable per run, of the wrong type or out of range",
                  "verification.min_final_confidence must be between 0 and 100"),
            **dict([RATE_429]),
        }),
    ("GET", f"{V1}/{{run_id}}/status"): Endpoint(
        "Runs", "Run status and progress",
        f"""
Poll this (about once a minute) until `pipeline.status` is `success`, `failed`
or `cancelled`.

* `pipeline`: `status` (`queued`, `running`, `success`, `failed`, `cancelled`),
  `started_at`, `finished_at`, `input_kind`, and for a successful run
  `completeness`: `complete`, `partial` (a stage ran out of its time limit,
  named in `partial_stages`; molecules handled after the limit may lack
  matches) or `incomplete` (database lookups failed, listed in `incomplete`).
  A partial or incomplete run still has `status` `success`: check
  `completeness` before treating its results as final.
* `tasks`: the pipeline stages (load, repair, signatures, identification,
  verification, export, render) with their status and a short summary.
* `progress` (once the molecules are known): `molecules_done` of
  `molecules_total`, and per molecule `waiting`, `searching` or `searched`.
* `warnings` and `critical_errors`: each has a `code`, a `message`, `details`
  (often `segment` and `service`) and a `docs_url` explaining it
  ([Warnings and errors]({DOCS}/warnings/)). A successful run can carry
  warnings, e.g. a database that did not answer.
* `incomplete`: lookups that failed for a reason another attempt can fix
  (server error, busy, timeout, a stage's time limit); `POST /rerun` repeats them.
* `retry` / `attempts`: automatic retries (repository queue only; not for time
  limits, which a run under the same limit would hit again). While a run
  waits for its next attempt its status reads `queued`.
* `retention`: when the run will be deleted (`expires_at`) and how the owner
  can extend it (`owner_choices`).

`?since=` returns only warnings, errors and events recorded at or after that
time; `tasks` and `progress` are always complete.""",
        example="status",
        params={"since": "ISO 8601 date or time, e.g. `2026-11-08T23:55:00Z` (no zone = UTC; "
                         "write `+` as `%2B`). Only warnings, errors and events from then on."},
        errors=dict([RUN_404])),
    ("GET", f"{V1}/{{run_id}}/queue"): Endpoint(
        "Runs", "Queue position",
        "Where a run stands: `state` is `queued`, `running` or `done`. While queued, "
        "`position` is its place in the queue (1 = next) and `ahead` the number of runs "
        "before it. Cheaper than `/status` for waiting.",
        example="queue",
        more_examples={"queued": ("A queued run", {"state": "queued", "position": 3, "ahead": 2})},
        errors=dict([RUN_404])),
    ("GET", f"{V1}/{{run_id}}"): Endpoint(
        "Runs", "Run summary",
        "A short summary: status, times, input kind, run name, and the numbers of "
        "pipeline stages, warnings, errors and incomplete lookups. `completeness` "
        "(`complete`, `partial` or `incomplete`; null until the run succeeded) and "
        "`partial_stages` say whether a successful run is complete: see `/status`. "
        "`retention` says how long the run is kept. For the details use `/status`.",
        example="summary",
        more_examples={"partial": ("A run whose database search ran out of time", PARTIAL_SUMMARY)},
        errors=dict([RUN_404])),
    ("GET", V1): Endpoint(
        "Managing runs", "Your runs",
        "The runs submitted from your network address, newest first: what the web "
        "application shows under *Your annotations*. Other people's runs are never listed. "
        "Runs are not tied to an account, so a different network (home, VPN) shows "
        "different runs. `completeness` and `partial_stages` as in `/status`.",
        example={"runs": [{"run_id": EXAMPLE_RUN, "status": "success",
                           "created_at": "2026-11-08T23:50:46.638453+00:00", "input_kind": "pdb",
                           "run_name": "Trypsin with benzamidine", "creator_ip": None, "queue": "web",
                           "completeness": "complete", "partial_stages": []}]},
        params={"mine": "Accepted for compatibility; only your own runs are ever listed."}),
    ("GET", f"{V1}/examples"): Endpoint(
        "Service", "Example runs",
        "The finished example analyses shown on the front page, with their pictures "
        "(`image_url` is a path on this host). They are kept permanently and are good "
        "test data for a client.",
        example="examples",
        params={"limit": "At most this many (1–10)."}),
    ("POST", f"{V1}/{{run_id}}/cancel"): Endpoint(
        "Managing runs", "Cancel a run",
        "Stops a queued or running run; its status becomes `cancelled`. A run waiting for "
        "an automatic retry keeps the results of its last attempt (status `success`).",
        example={"run_id": "7b0e5f2c-3d41-4a8e-9f61-2c8d0a4b5e17", "status": "cancelled"},
        params={"X-Owner-Token": OWNER_TOKEN},
        errors={400: ("The run has finished already", "Run is already in terminal state: success"),
                403: _owner("cancelled")[1], **dict([RUN_404])}),
    ("POST", f"{V1}/{{run_id}}/rerun"): Endpoint(
        "Managing runs", "Run again",
        "Starts a new run with the same input files and settings, applied over today's "
        "server settings (lookups that worked before come from the cache, so in practice "
        "only failed ones are repeated). Anyone with the run id can rerun it; the answer is "
        "the new run with its own `owner_token`.\n\n"
        "With the old run's `X-Owner-Token`, the new run goes to the same queue and the old "
        "one is marked `superseded_by` the new one. A body `{\"preset\": \"deep\"}` runs "
        "the files with that preset on today's settings instead of the old choices. NCBI "
        "nr/nt/core_nt are searched again only when the old run used Deep search. The new "
        "run is kept for the default 30 days.",
        example={**CREATED, "message": "Run 7b0e5f2c-3d41-4a8e-9f61-2c8d0a4b5e17 queued successfully"},
        body_example={"preset": "deep"},
        params={"X-Owner-Token": "Optional: " + OWNER_TOKEN},
        errors={404: ("No run with this id, or its input files are gone",
                      f"Run '{EXAMPLE_RUN[:8]}…' has no input files to re-run"),
                422: ("Unknown preset", "Unknown preset: fast (one of balanced, quick, exact, deep)"),
                **dict([RATE_429])}),
    ("POST", f"{V1}/{{run_id}}/retention"): Endpoint(
        "Managing runs", "Keep a run longer",
        "Finished runs are deleted 30 days after they finish. The owner can keep one "
        "30, 90, 180 or 365 days counted from now; this only ever extends. Example runs "
        "and runs submitted with `retention=preserve` are kept permanently.",
        example={"policy": "days", "days": 90, "expires_at": "2027-02-17T10:12:03+00:00",
                 "example": False, "owner_choices": [30, 90, 180, 365]},
        body_example={"days": 90},
        params={"X-Owner-Token": OWNER_TOKEN},
        errors={400: ("`days` is not 30, 90, 180 or 365", "days must be one of 30, 90, 180, 365"),
                403: _owner("kept longer")[1],
                409: ("The run has not finished, is kept permanently, or is already kept "
                      "longer than that", "This run is already kept until 2027-05-18."),
                **dict([RUN_404])}),
    ("DELETE", f"{V1}/{{run_id}}"): Endpoint(
        "Managing runs", "Delete a run",
        "Deletes the run and all its files at once; this cannot be undone. Cancel a queued "
        "or running run first; it can be deleted right after the cancel.",
        example={"message": "Run '7b0e5f2c-3d41-4a8e-9f61-2c8d0a4b5e17' deleted successfully"},
        params={"X-Owner-Token": OWNER_TOKEN},
        errors={403: ("No or wrong owner token, or an example run", "Example runs cannot be deleted."),
                409: ("The run is queued or running",
                      "This run is still queued or running: cancel it first, then delete it."),
                **dict([RUN_404])}),
    # ------------------------------------------------------------- Results
    ("GET", f"{V1}/{{run_id}}/molecules"): Endpoint(
        "Results", "Molecules",
        "What the system is made of. `segments` lists the distinct molecules by "
        "`segment` name: the name every other call uses (`?segment=`). `segment_meta` "
        "gives each one's display name (residue name for small molecules), type, number "
        "of `copies` (e.g. 62 waters are one molecule with 62 copies), atoms per copy and "
        "chain. `type_counts` counts the molecules by type: `protein`, `nucleic`, "
        "`small_molecule`, `lipid`, `glycan`, `ion`, `water`.",
        example="molecules", errors=dict([RUN_404])),
    ("GET", f"{V1}/{{run_id}}/molecules/{{segment}}/info"): Endpoint(
        "Results", "One molecule",
        "One molecule in brief: display name, type, atom and residue counts and the "
        "confidence (0–100) of its best verified identification, as in results.csv. "
        "`confidence` is null when nothing was verified and for exact answers (ions, water).",
        example="molecule_info",
        params={"segment": "A `segment` from `/molecules`."},
        errors={404: ("No run with this id, or no such molecule in it", "Segment 'ZZ' not found")}),
    ("GET", f"{V1}/{{run_id}}/verification"): Endpoint(
        "Results", "Identifications",
        f"""
**The main result.** For each molecule, the database candidates after
verification: first the verified ones (`is_verified: true`) in the order the
results page shows them, then the rejected ones with their `rejection_reason`.

* `identifier`, `database`, `database_url`: the record, with a link.
* `name`, `organism`: what the record is.
* `final_confidence` (0–100): how sure BioID is that this record is this
  molecule (≥ 80 high, ≥ 50 medium). It combines `resolver_score` (how
  well the search matched), `similarity_score` (how well the record's own
  structure or sequence matches the molecule) and `annotation_quality_score`
  (how well the record is annotated).
* `ground_truth_override`: set for exact answers (ions, water), which have no
  confidence to weigh.
* `equivalence_class_id`: records with the same id describe the same verified
  structure (e.g. one compound in PubChem and ChEMBL).

The best identification of a molecule is its verified hit with the highest
`final_confidence`. How the scores are computed:
[Identification & verification]({DOCS}/identifiers/).""",
        example="verification",
        more_examples={"segment": ("One molecule: ?segment=A__v1", "verification_segment")},
        params={"segment": SEGMENT_FILTER},
        errors=dict([RUN_404])),
    ("GET", f"{V1}/{{run_id}}/identifiers"): Endpoint(
        "Results", "Database hits",
        "Every raw hit of every database search, before verification: which search "
        "(`resolver_name`; `@sim` = similarity search) found which record, with BLAST "
        "`evalue`, `bit_score`, `identity_percent` and `coverage_percent` where they apply. "
        "`hit_type` is `identity` for exact matches and `similarity` for similar ones. "
        "`attempted_resolvers` lists the searches run, `failed_resolvers` those that failed "
        "(with the reason). Large: thousands of hits for a protein.",
        example="identifiers",
        params={"segment": SEGMENT_FILTER},
        errors=dict([RUN_404])),
    ("GET", f"{V1}/{{run_id}}/signatures"): Endpoint(
        "Results", "Signatures",
        "The descriptions BioID generated for each molecule and searched with: `generator` "
        "names the kind (`smiles`, `inchi_key`, `molecular_formula`, `fasta_map_protein` "
        "(sequence), `resname`, `mmcif`, `ca_only_pdb`, …) and `signature` is the value, "
        "which can be a whole structure file. `attempted_generators` lists, per molecule, "
        "the kinds BioID tried.",
        example="signatures",
        params={"segment": SEGMENT_FILTER}, errors=dict([RUN_404])),
    ("GET", f"{V1}/{{run_id}}/download/results.csv"): Endpoint(
        "Results", "results.csv",
        "One row per molecule: display name, type, copies, atoms, `Result` (`identified`, "
        "`lead` = verified but confidence below 50, `exact` for ions and water, "
        "`not identified`), the best identification with its database, link and confidence, "
        "and up to three alternatives (`Database:identifier`).",
        example="results_csv", media="text/csv", returns="CSV, as a download",
        errors=dict([RUN_404])),
    ("GET", f"{V1}/{{run_id}}/download/results.json"): Endpoint(
        "Results", "results.json",
        f"The complete record of the run: `pipeline`, `tasks`, `warnings`, "
        f"`critical_errors`, `events` and `data` (molecules, signatures, every search and "
        f"verification). Structure: [results.json reference]({DOCS}/results-json/). "
        "Several MB for a large system; the other Results calls give the same data in parts.",
        example={"pipeline": {"run_id": EXAMPLE_RUN, "status": "success", "...": "…"},
                 "tasks": ["…"], "warnings": ["…"], "critical_errors": [], "events": ["…"],
                 "data": {"universe": "…", "fragments": "…", "signatures": "…",
                          "identifiers": "…", "verification": "…"},
                 "created_at": "2026-11-08T23:50:46.638453+00:00",
                 "updated_at": "2026-11-08T23:58:37.460808+00:00", "artifacts": {}},
        returns="JSON, as a download (shortened here)",
        errors=dict([RUN_404])),
    ("GET", f"{V1}/{{run_id}}/loading"): Endpoint(
        "Results", "How the files were read",
        "Which reader BioID used for the input (`selected_strategy`), each one it tried "
        "(`attempts`, with the error of those that failed), and why loading failed "
        "(`failure_summary`) for a run that stopped there.",
        example="loading", errors=dict([RUN_404])),
    # --------------------------------------------------------------- Files
    ("GET", f"{V1}/{{run_id}}/files"): Endpoint(
        "Files", "Run files",
        "Every file of the run, as paths to fetch from `/files/{run_id}/<path>`: the "
        "uploaded inputs (`input/`), the structure of each molecule (`<segment>.mmcif`), "
        "the whole system (`system.mmcif`), pictures (`render/`), the logs and "
        "`results.json`.",
        example="files", errors=dict([RUN_404])),
    ("GET", f"{V1}/{{run_id}}/render"): Endpoint(
        "Files", "Structures and pictures",
        "Paths (under `/files/{run_id}/`) of the whole-system mmCIF and picture and of each "
        "molecule's, plus `segment_selectors`: where each molecule is in the system "
        "structure (chains, 0-based atom index ranges `[start, end)`, residue ranges), for "
        "highlighting it in a viewer.",
        example="render", errors=dict([RUN_404])),
    ("GET", f"{V1}/{{run_id}}/logs"): Endpoint(
        "Files", "Run log",
        "The run log as text; `?type=debug` for the verbose one. \"Logs not available yet.\" "
        "before the run starts.",
        example="logs", media="text/plain", returns="Plain text",
        params={"type": "`normal` (default) or `debug`."},
        errors=dict([RUN_404])),
    ("GET", f"{V1}/{{run_id}}/download/topology-less-pdb"): Endpoint(
        "Files", "Molecule as PDB",
        "One molecule's structure as a PDB file (no topology records), as BioID used it "
        "for structure searches. Pass `segment` when the run has several molecules "
        "with such a structure.",
        example="topology_less_pdb", media="chemical/x-pdb", returns="PDB text",
        params={"segment": "The molecule (a `segment` from `/molecules`)."},
        errors={400: ("Several molecules and no `segment`",
                      "Multiple segments found (A, B), specify segment parameter"),
                404: ("No run with this id, or no such structure for this molecule",
                      "Segment 'A__v3' not found or has no topology-less-pdb signature")}),
    ("GET", f"{V1}/{{run_id}}/download/ca-only-pdb"): Endpoint(
        "Files", "Protein Cα trace as PDB",
        "One protein's Cα atoms as a PDB file, as BioID used it for fold searches. Pass "
        "`segment` when the run has several proteins.",
        example="ca_only_pdb", media="chemical/x-pdb", returns="PDB text",
        params={"segment": "The protein (a `segment` from `/molecules`)."},
        errors={400: ("Several proteins and no `segment`",
                      "Multiple segments found (A, B), specify segment parameter"),
                404: ("No run with this id, or no Cα trace for this molecule",
                      "Segment 'A__v1' not found or has no ca-only-pdb signature")}),
    # ------------------------------------------------------- Configuration
    ("GET", f"{V1}/config/options"): Endpoint(
        "Settings", "Presets and settings",
        f"""
`config`: every setting a run may change, by section, with the server's
values. `identifiers` switches the database searches on and off (each has a
`_similarity` twin for similar, not only exact, matches; see
[Databases]({DOCS}/databases/)); `verification` sets how many candidates are
verified and the confidence threshold.

`presets`: `balanced` (the server's settings), `quick` (no slow structure and
NCBI searches), `exact` (exact matches only) and `deep` (adds NCBI nr/nt; hours
per protein), each with the `overrides` it applies.

Submit with `preset` and/or `config_json` containing only what you change.""",
        example="config_options", returns="Settings and presets (shortened here)"),
    # ------------------------------------------------------------- Service
    ("GET", "/api/v1/capabilities"): Endpoint(
        "Service", "Capabilities",
        "The deployed code version, the typical run duration in minutes, and the API "
        "features this server has (`additions`), for clients that must work with older "
        "deployments.",
        example="capabilities"),
    ("GET", "/api/v1/health"): Endpoint(
        "Service", "Health", "Answers `healthy` while the API is up.", example="health"),
    ("POST", f"{V1}/{{run_id}}/reports"): Endpoint(
        "Results", "Report a wrong identification",
        "Tells the BioID team that a molecule's identification looks wrong, optionally with "
        "what it really is. No token needed; at most 20 reports per network address per hour. "
        "The team reviews every report.",
        example={"id": "20261119T101203-3fa2c1",
                 "message": "Thank you. The BioID team will look at it."},
        body_example={"segment": "A__v1", "note": "The ligand of 3PTB is benzamidine.",
                      "suggestion": "PubChem CID 2332"},
        returns="The report was recorded",
        errors={404: ("No run with this id, or no such molecule in it",
                      f"Run '{EXAMPLE_RUN[:8]}…' has no molecule 'ZZ'."),
                429: ("More than 20 reports from your address this hour",
                      "Too many reports from your network address this hour. Please try again later.")}),
}

#: Swagger lists the operations of a tag in the order of their paths, so this
#: order is the reading order within each tag. Operations sharing a path stay
#: together: /runs/{run_id} (GET summary, DELETE) comes after retention so
#: that the summary closes "Runs" and deleting closes "Managing runs".
PATH_ORDER = [
    V1, f"{V1}/{{run_id}}/status", f"{V1}/{{run_id}}/queue",
    f"{V1}/{{run_id}}/molecules", f"{V1}/{{run_id}}/molecules/{{segment}}/info",
    f"{V1}/{{run_id}}/verification", f"{V1}/{{run_id}}/identifiers", f"{V1}/{{run_id}}/signatures",
    f"{V1}/{{run_id}}/download/results.csv", f"{V1}/{{run_id}}/download/results.json",
    f"{V1}/{{run_id}}/loading", f"{V1}/{{run_id}}/reports",
    f"{V1}/{{run_id}}/files", "/files/{run_id}/{path}", f"{V1}/{{run_id}}/render",
    f"{V1}/{{run_id}}/logs", f"{V1}/{{run_id}}/download/topology-less-pdb",
    f"{V1}/{{run_id}}/download/ca-only-pdb",
    f"{V1}/{{run_id}}/cancel", f"{V1}/{{run_id}}/rerun", f"{V1}/{{run_id}}/retention",
    f"{V1}/{{run_id}}",
    f"{V1}/config/options",
    f"{V1}/examples", "/api/v1/capabilities", "/api/v1/health",
]


def _files_path() -> dict[str, Any]:
    """/files/{run_id}/<path> is served by a static-files mount, not a route:
    documented here only."""
    return {
    "/files/{run_id}/{path}": {"get": {
        "tags": ["Files"], "summary": "A file of a run",
        "operationId": "get_run_file",
        "description": (
            "Any file listed by `GET /api/v1/runs/{run_id}/files` (note: no `/api/v1` prefix), "
            "e.g. `system.mmcif`, `render/system.png`, `A.mmcif` or `results.log`. Supports "
            "`Range`, `ETag` and `If-None-Match`. `results.json` here is the file as stored; "
            "`/api/v1/runs/{run_id}/download/results.json` leaves out the submitter's "
            "hashed address and owner-token hash."),
        "parameters": [
            {"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"},
             "example": EXAMPLE_RUN, "description": "The run id"},
            {"name": "path", "in": "path", "required": True, "schema": {"type": "string"},
             "example": "render/system.png", "description": "A path from `/files`"}],
        "responses": {
            "200": {"description": "The file; the type follows the extension",
                    "content": {"application/octet-stream": {"schema": {"type": "string",
                                                                       "format": "binary"}}}},
            "404": _error_response("No such run or file", "Not Found")}}}}


def _example(value: Any, ex: dict[str, Any]) -> Any:
    return ex[value] if isinstance(value, str) and value in ex else value


def _error_response(when: str, detail: str) -> dict[str, Any]:
    return {"description": when, "content": {"application/json": {
        "schema": {"$ref": "#/components/schemas/ErrorResponse"},
        "example": {"detail": detail}}}}


def publish(app) -> None:
    """Publish ENDPOINTS in app's schema; every other route is left out."""
    from fastapi.routing import APIRoute
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        ep = next((ENDPOINTS[(m, route.path)] for m in route.methods if (m, route.path) in ENDPOINTS), None)
        if ep is None:
            route.include_in_schema = False
            continue
        route.tags, route.summary, route.description = [ep.tag], ep.summary, ep.description

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            from fastapi.openapi.utils import get_openapi
            schema = get_openapi(title=app.title, version=app.version, description=API_DESCRIPTION,
                                 routes=app.routes, tags=TAGS)
            app.openapi_schema = annotate(schema, examples())
        return app.openapi_schema

    app.openapi = openapi


def annotate(schema: dict[str, Any], ex: dict[str, Any]) -> dict[str, Any]:
    """Add the parameter descriptions, errors and examples of ENDPOINTS."""
    schema = copy.deepcopy(schema)
    schema.setdefault("components", {}).setdefault("schemas", {})["ErrorResponse"] = {
        "title": "ErrorResponse", "type": "object", "required": ["detail"],
        "description": "Every error answer: a JSON object with a human-readable `detail`.",
        "properties": {"detail": {"title": "Detail", "type": "string",
                                  "description": "What went wrong, and usually what to do about it"}}}
    for (method, path), ep in ENDPOINTS.items():
        op = schema["paths"].get(path, {}).get(method.lower())
        if op is None:
            continue
        for p in op.get("parameters", []):
            if p["name"] in ep.params:
                p["description"] = ep.params[p["name"]]
                p.get("schema", {}).pop("description", None)
            if p["name"] in PARAM_EXAMPLES and p["in"] in ("path", "query"):
                p["example"] = PARAM_EXAMPLES[p["name"]]
        responses = op.setdefault("responses", {})
        ok_code = next((c for c in responses if c.startswith("2")), "200")
        ok = responses.setdefault(ok_code, {})
        ok["description"] = ep.returns
        if ep.example is not None:
            media = ep.media or "application/json"
            content = ok.setdefault("content", {})
            if ep.media:
                content.pop("application/json", None)
                content.setdefault(media, {"schema": {"type": "string"}})
            body = content.setdefault(media, {})
            if ep.more_examples:
                body["examples"] = {"run": {"summary": "Trypsin example run", "value": _example(ep.example, ex)}}
                for name, (summary, value) in ep.more_examples.items():
                    body["examples"][name] = {"summary": summary, "value": _example(value, ex)}
            else:
                body["example"] = _example(ep.example, ex)
        if ep.body_example is not None:
            rb = op.get("requestBody", {}).get("content", {}).get("application/json")
            if rb is not None:
                rb["example"] = ep.body_example
        responses.pop("422", None)  # FastAPI's generic validation error; listed below when it applies
        for code, (when, detail) in sorted(ep.errors.items()):
            responses[str(code)] = _error_response(when, detail)
    paths = {**schema["paths"], **_files_path()}
    schema["paths"] = {p: paths[p] for p in sorted(paths, key=lambda p: PATH_ORDER.index(p)
                                                    if p in PATH_ORDER else len(PATH_ORDER))}
    return schema
