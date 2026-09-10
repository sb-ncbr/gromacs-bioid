# Concept: The Three API Copies (root = LIVE)

## Core Concept
The repo contains THREE divergent copies of the validation API/scheduler code. Deployments import only ONE of them. Editing the wrong copy changes nothing in production.

## The Copies
| Location | Role | Status |
|---|---|---|
| repo ROOT: `main.py`, `queue_processor.py`, `models.py`, `tasks.py`, `config.py`, `mddbr_client.py`, `api/failure_analysis.py` | **LIVE**: flatten-built into images; `validation-api` runs `uvicorn main:app` from `/app` | canonical |
| `src_new/api/` | BAT3 pipeline API (`run_pipeline_task`, `/stats`, `/runs`) — ALSO imported via `sys.path.insert(0,'/app')` tricks | live for pipeline, no scheduler |
| `validation/api/` (via `validation/` symlink → `../bat3_validation/`) | mirror copy with enhancements modules (`indexing_enhancements`, `gt_enhancements`) | divergent; docker context for smaller images |

## Key Points
- v3.81-era api pods ran `uvicorn src_new.api.main:app` (workingDir `/app/src_new`) = **no background scheduler** — dispatch silently died after the Aug-13 rollout (0 new runs for a month, signature of P1 stall)
- Fixed deployment runs `uvicorn main:app` at `/app` → scheduler (APScheduler 30s tick) restored
- `Dockerfile.full` (validation/api/) builds repo-root context; flattened modules already exist at root
- The `validation/` dir itself is a SYMLINK to `../bat3_validation/` (external) — not committed; deploy scripts copy content into images, never rely on the symlink inside containers
- Models↔DB schema drift is invisible at runtime until a mapped column is needed (retry_count/last_error were in DB but unmapped → error text silently dropped)

## Rule
**Make scheduler/queue edits in the ROOT copies first**, then mirror into `validation/api/` when building that context. Verify which entrypoint the deployment uses (`kubectl get deploy ... -o jsonpath='{.spec.template.spec.containers[0].command}'`) before assuming where code runs.

## Reference
- `../lookup/ceitec-deployment.md`
- `bat3_validation/docs/INCIDENT_REGISTRY_2026-09.md` (P1-8, root-cause archaeology section)
