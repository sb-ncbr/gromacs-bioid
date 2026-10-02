# SESSION RESUME — BioID UI Rework (compaction-ready)

## State: COMPLETE, in production; post-cutover polish waves W8–W10 shipped (panel bottom-align via absolute decoupling w9, merged Name/Identifier column w10). Tip: cf4eee824 + w11 (501887476, verification-tab merged column parity; prod = w11 digest). HYGIENE DONE x2 - this file is the cold-start point
Live: web=bat3-frontend:production-v1 (digest = w10), api=bat3-api:ui-rework-b1, ingress WS7-fixed. Site: bioid-ceitec.dyn.cloud.e-infra.cz (200).

## What was built (all gated/user-verified)
Fresh `ui/` (Vite6+React19+TS strict+Tailwind v4+e-infra DS 0.1.9 pinned, BioID green theme); frontpage (upload, IP-bound recents, rerun/delete); results (TaskBar→warnings anchors, adaptive-polling hooks, segment selector w/ type icons, Mol* system-context single-instance w/ watchdog+PNG fallback+gray-missing state, stored-order verification panel bottom-aligned to viewer, tabs Overview/Input&Files/Signatures/Identifiers/Verification/Warnings with human copy from error catalog); API additive `/api/v1` (+creator_ip, ?mine=1, rerun, queue, canonical database_url); ingress deep-link fix (SPA on /, API on /api).

## Canonical knowledge (do not re-derive)
- `docs/BIOID_UI.md` — prod architecture/ops/rollback/landmines
- `.opencode/context/bat3/concepts/bioid-ui.md`, updated `lookup/ceitec-deployment.md`, `errors/common-issues.md` (P2 family), `navigation.md`
- `.tmp/tasks/ui-rework/`: PLAN.md (status+backlog), CONTEXT.md (coder rules), errors/error-catalog.json (copy source of truth), contracts/ (openapi baselines + PROVENANCE.md: source≡live), fixtures/, backups/, deploys.md (append-only), briefs/

## Discipline (violations = rework)
Additive-only API w/ additions-only openapi diff gate · worktree-only image builds · pipefail+preflight deploys · per-deliverable commits · stage-owned-files-only (OTHER WORKER ACTIVE on src_new backend — never touch their files) · verification hits = stored order verbatim · warning copy changes go through error-catalog.json.

## Way-later backlog (PLAN.md has detail)
docs link, server-side human names, dark mode, config presets, SOL water worker reclassification, 2 pre-existing API test failures, queue position accuracy, a11y/mobile, bundle chunks.

## Quick verify (cold start sanity)
curl -s -o /dev/null -w "%{http_code}\n" https://bioid-ceitec.dyn.cloud.e-infra.cz/   # 200
curl -s https://bioid-ceitec.dyn.cloud.e-infra.cz/api/v1/health                  # {"status":"healthy"}
git -C /home/tomsko/work/bat3 log --oneline -3 && git tag -l "ui-*"
