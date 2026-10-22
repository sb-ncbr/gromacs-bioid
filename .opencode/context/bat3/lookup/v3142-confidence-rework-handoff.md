# v3.142 / v3.142.1 Confidence-Scoring Rework — Wave Record (closed 2026-10-22)

> Audience: future agents resuming BAT3 work after compaction. Scope: what changed,
> why, final deploy/fixture IDs, tripwires learned the hard way, open leftovers.
> Gate adjudication detail: `.tmp/GATE_v3142.md`; calibration: `.tmp/CALIBRATION_v3142.md`.

## What shipped
6-phase plan (`.tmp/PLAN_v3142_confidence.md`, approved before implementation):
- **R-a resolver term = belief** `100·(1 − 0.5^(n_id + n_sim/3))`, κ=⅓, ρ=½ —
  calibrated on campaign corpus, capped 99.9999. Replaces residuum-consensus in the
  composition only (legacy capped `resolver_score` still stored for traceability).
- **M-a similarity = worker-primary**; skeleton-fp Tanimoto remains *corroboration
  gate* + fallback only.
- **1c annotation term**: uniform per-kind denominators + bounded live-API fill
  (`annotation_live_fetch=True` default, 25/segment, 3 s timeout, silent fallback).
- **Phase 2**: confidence always numeric (plateau-null from v3.140 REMOVED);
  breakdown tooltip in UI; additive `belief`/`skeleton_sim` export columns.
- **Phase 3**: weights normalized by sum at use-time (zero-sum → equal thirds);
  raw+effective weights recorded in `verification/_meta` — formula `v3.142.1`.
- **Phase 4**: equivalence-class collapse — every hit carries
  `equivalence_class_id` (`skeleton:<fp-hex>` cross-DB, `align:|tm:` rounded,
  `element:`, `record:` fallback); per-segment `class_sizes` map; ResultsPanel
  renders "1 verified structure — +N equivalent database records" (visual-only).
- **Phase 5**: projection gate adjudicated (below), deployed, E2E green; then
  **v3.142.1** polish: warning severities (info codes don't flip task status),
  segment-tagged signature warnings, verification-tab molecule selector.

## Gate adjudication (user-approved — do NOT relitigate)
D-chain replay over 5,993 annotations: v3.142 conf only reorders *slot‑4 ties*
among evidence-identical plateau rows. 9/5,652 cache-reliable annotations differ
(±0.01–0.16 pp, 7−/2+). Accepted as within-noise; Phase‑4 collapse absorbs the
UI-visible difference. Evidence: NFS mirror `/data/validation/calibration_v3142/`
(`stage_6/7/8_*`), scripts `.tmp/projection_v3142*.py`, `.tmp/diag_v3142.json`.

## Final deployed state (ceitec)
- Backend image `cerit.io/tomsko/bat3-validation-api@sha256:f3a19d3a` (tag v3.142,
  **Dockerfile.full build** — pymol present). Deploys: bat3-ceitec-bat3-api /
  -worker ×15 / bat3-ui-worker (all digest-pinned).
- Web `cerit.io/tomsko/bat3-frontend@sha256:82444e0e` (tag w19).
- E2E proof runs: `456d0bab-…` (10/12, pre-fix) then **`41db1f7c-707a-4f90-9776-e47c13488447`
  battery ALL OK (12/12)**, all tasks success, pymol rendered. Battery:
  `bash .tmp/e2e_assert_v3142.sh <run_id>`.
- Reference baseline run (v3.141): `6258aee6-a4e4-4e3c-a51e-20dbf4b2b5fc` — E2E
  reruns always branch from this (never retro-edit old runs).

## Suites baselines (must stay green)
backend+pipeline **248** · loader **199** · UI **126** + `npx tsc -b` clean ·
api+executor = **4 pre-existing reds, verified on pre-wave commit** (`test_get_run_molecules`,
`test_post_runs_with_config`, `test_verification_worker_returns_verified_hits`,
`test_full_pipeline_protein_id`) — do not mix these up with regressions.

## Tripwires hit this wave (consult before similar work)
- **Type gate**: root `ui/tsconfig.json` is references-only ⇒ `npx tsc --noEmit`
  is a *silent no-op*. Real gate = `npx tsc -b` (what `npm run build`/Docker run).
- **Persistence**: parallel `verify_results` workers own a throwaway temp
  ResultsManager per segment — only `verified_hits` return. Anything to persist
  (meta, class_sizes) must be written by the STEP merge loop
  (`src_new/pipeline_steps/__init__.py`).
- **Backend image canon**: `Dockerfile.full` (3 GB, content gate incl.
  `which pymol`), NOT `Dockerfile.api` — a thin-image deploy broke PNG rendering;
  playbook amended.
- **pkill self-match**: patterns that appear in the caller's own cmdline SIGTERM
  your shell — split steps / bracket trick (`stat[u]s`).
- **kubectl port-forwards die on api rollouts** → always recreate before E2E;
  `pgrep -af "port-forwar[d]"` to check.
- Pipeline status vocabulary: `success` (not `completed`).
- Deployed pods: rollouts verify via imageID, not tag (same-tag push = spec no-op).

## Leftovers (user decisions pending)
- Untracked `.opencode/` scaffolding + `opencode.json` local mod (context-system
  bits) — keep/commit/discard? **Open.**
- Single-segment pane click-test (run `4964c437`) still open.
- Optional display note: ≤3-atom molecules' iDSM similarity saturates ≈40% by
  design (water pin row) — consider a UI hint (user has the full story).
- Red-team intake: see `.tmp/PICKUP_redteam_fix.md` (next wave).
