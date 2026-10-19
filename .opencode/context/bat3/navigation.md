# BAT3 Context Navigation

## Core Concept
Quick entry point to all BAT3 context files. Use this to find verification commands, status, and troubleshooting guides.

## Key Points
- **Status check**: `lookup/status.md` — deployment state (2026-09-10/23 era, **stale for paper numbers** — use publication-v14-numbers)
- **Paper numbers (v14 canonical)**: `lookup/publication-v14-numbers.md` — every quotable number + source artifact (2026-10-07 harvest)
- **Publication session ledger**: `lookup/publication-journal.md` — chronological paper-work history
- **§3.4 beyond-GT measurement**: `lookup/beyond-gt-measurement-handoff.md` — pipeline, traps, wording constraints (2026-10-12)
- **Live deployment**: `lookup/ceitec-deployment.md` — images (UI: production-v1, API: ui-rework-b1), mounts, paths, ingress routing, gotchas
- **Debug issues**: `errors/common-issues.md` — incident failure signatures P0-1..P0-6 + P1 family
- **Reprocess/score**: `guides/validation-reprocessing.md`
- **Upgrade safely**: `guides/safe-helm-upgrade.md` (kubectl-set drift)
- **Where code runs**: `concepts/code-layout.md` — THREE api copies, root = live
- **Full forensic log**: `bat3_validation/docs/INCIDENT_REGISTRY_2026-09.md` (external dir)

## Quick Links

| Purpose | File |
|---------|------|
| Current status | `lookup/status.md` |
| Live deployment facts | `lookup/ceitec-deployment.md` |
| All commands | `commands.md` |
| Start validation | `guides/running-validation.md` |
| Reprocess + score | `guides/validation-reprocessing.md` |
| Safe helm upgrade | `guides/safe-helm-upgrade.md` |
| Index MDDBR | `guides/indexing-mddbr.md` |
| Incident error signatures | `errors/common-issues.md` |
| Code layout (3 api copies) | `concepts/code-layout.md` |
| Web UI (post-rework) | `concepts/bioid-ui.md` + `docs/BIOID_UI.md` |
| Example run | `examples/run-batch.md` |
| What is BAT3 | `concepts/bat3.md` |
| Validation pipeline | `concepts/validation.md` |
| Publication (NM paper) | `lookup/publication-journal.md` |
| Loading strategy (MD coverage widening) | `concepts/loading-strategy.md` |
| Static render pipeline (worker PNGs / Mol* fallback / examples) | `concepts/static-render-pipeline.md` |
| Pipeline dispatch & crash robustness (OQ-16 model) | `concepts/pipeline-dispatch-and-reaper.md` |
| S0 signature-stage validation (case file) | `lookup/s0-signature-stage-case-file.md` |
| Failure-mode audit report + data links (journal handoff) | `lookup/failure-mode-audit-handoff.md` |
| MDDBR GT curation handoff (A5 cohorts) | `lookup/a5-curation-handoff.md` |
| Automatic-annotation motivation (A4 perception gap) | `lookup/a4-perception-gap-handoff.md` |
| Stats harvester ops playbook (pods/NFS hazards) | `guides/stats-pods-operations.md` |

## Reference
- `concepts/bat3.md` - BAT3 overview
