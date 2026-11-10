# BioID

BioID identifies the molecules in a molecular dynamics simulation. From the
simulation files (GROMACS, AMBER, CHARMM/NAMD, LAMMPS, PDB/mmCIF) it finds
the proteins, nucleic acids, ligands, lipids, glycans and ions, searches
sequence, structure and chemical databases for each of them, and re-checks
every candidate against its database record before reporting it with a
confidence from 0 to 100.

The codebase's internal name is **BAT3**; you will see it in module, image
and deployment names.

## Links

| | |
|---|---|
| Web application | <https://bioid-ceitec.dyn.cloud.e-infra.cz/> |
| Documentation | <https://bioid-ceitec.dyn.cloud.e-infra.cz/documentation/> (source in `docs/site/`) |
| REST API reference (Swagger) | <https://bioid-ceitec.dyn.cloud.e-infra.cz/docs> |
| MCP server for AI assistants | `https://bioid-ceitec.dyn.cloud.e-infra.cz/mcp` ([setup](https://bioid-ceitec.dyn.cloud.e-infra.cz/documentation/mcp/)) |

The service runs on the e-INFRA CZ / CERIT-SC Kubernetes cloud for CEITEC.

## Repository layout

| Path | What |
|---|---|
| `src_new/` | the pipeline (loading, signatures, database searches, verification, export) and the FastAPI service `src_new.api.main:app` |
| `ui/` | the web application (React, Vite, Mol*) |
| `mcp_server/` | the MCP server, a client of the public REST API |
| `tests/` | pytest suites (`tests/src_new/`, `tests/mcp_server/`, …) |
| `scripts/` | database builders, statistics and audit tools (`scripts/stats/`) |
| `docs/site/` | the documentation site (mkdocs); other files in `docs/` describe older states of the code |
| `bat3-chart/` | Helm chart: API, web, fleet worker, main ingress |
| `deploy/` | manifests outside the chart: UI worker, MCP server, docs, extra ingress paths, nginx configs |
| `k8s/` | Jobs that build the local databases (BLAST, Foldseek, PubChem mirror, reference indexes) |
| `config.ini` | settings of the public service's runs |
| `Dockerfile.full`, `.frontend`, `.mcp`, `.docs` | the images in use (backend, web, MCP, docs) |
| `main.py`, `queue_processor.py`, `models.py`, `tasks.py` | the validation-campaign control plane (dormant since October 2026) |

Legacy, not used by the deployed service: `src/` (previous pipeline),
`web/` (previous web UI), `cli/`, `api/`, `__old_deployment/`,
`Dockerfile.{api,worker,web,ui}`. `validation` is a symlink to a separate
repository (the campaign UI) and dangles in a fresh clone.

## Development quick start

Python 3.11 and Node.js 22.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e '.[dev]'

# tests (from the repository root)
.venv/bin/python -m pytest tests/src_new -q
(cd ui && npm ci && npx vitest run)
```

Some tests need the local BLAST databases, GROMACS fixtures or network
access, and fail without them.

Run the API and the web application locally:

```bash
# Celery broker for the run queue
docker run -d -p 6379:6379 redis:8-alpine
export CELERY_BROKER_URL=redis://localhost:6379/0 CELERY_RESULT_BACKEND=redis://localhost:6379/0

.venv/bin/uvicorn src_new.api.main:app --port 8000                          # API
.venv/bin/celery -A src_new.celery_app worker --pool=threads --concurrency=2 # worker, second shell
cd ui && npx vite                                                           # UI, third shell
```

Vite serves the UI on <http://localhost:5173> and proxies `/api`, `/runs`,
`/files` and `/health` to the API on port 8000. Database locations are set in
`config.ini`; without the local databases only the remote searches run. See
[Developers](https://bioid-ceitec.dyn.cloud.e-infra.cz/documentation/developers/)
for more.

## Citation

A paper describing BioID is in preparation.

## Contact

Tomáš Pavlík — [tomas.pavlik@muni.cz](mailto:tomas.pavlik@muni.cz)
