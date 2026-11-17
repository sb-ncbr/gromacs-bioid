# UI redesign fork — resume card (2026-10-26)

> Pick up here after network reset. This fork's scope: **UI code + UI deployment only.** Everything else read-only without user authorization. Parallel fork owns validation/methodology (D-13 adjudication state lives in `.tmp/redteam/TODO.md`).

## Status update — 2026-10-27

**The redesign is DONE and LIVE.** All phases of the reviewer handoff
(`bat3_article_reviews/bioid_ui_handoff/`) landed on master. `/runs/:id` is
fully replaced in place: run header → error banner → status strip (+notes) →
molecule list | stage (answer header, per-kind Mol\* canvas, tabs) → technical
details fold → citation/retention line. Suite 267/267, tsc + eslint clean,
production build passes.

**Deployed 2026-10-26** as `cerit.io/tomsko/bat3-frontend:w21-redesign` (built
from clean worktree @ `24d9d5af2`; unique tag, pod imageID digest-verified,
live HTML asset parity confirmed). Rollback = one `set image` back to `w20`
(`@sha256:3bfc07122c92f…`).

## TODO

- [ ] **In-browser acceptance (user, ~20 min)** — the 4 items static analysis
      can't cover: <15 Tab to first molecule row · dark-theme contrast on
      pills/notes · 1440×900 header+canvas-top visibility · reduced-motion feel.
      Any failure is a small UI-only fix.
- [ ] **Backend gaps handoff (user coordinates)** — `ui/BACKEND_GAPS.md` → API
      fork. Priority G5 (hit names on verified hits), then G4/G3/G2/G1/G6/G9/G8.
      The page upgrades automatically as they land (fallbacks shipped).
- [ ] **Legacy cleanup decision (user)** — retire `MolstarViewer.tsx`,
      `MoleculeSelector.tsx`, `ResultsPanel.tsx` (alive only via the DEV-gated
      playground `src/dev/FixturesPlayground.tsx`) → rewrite/remove playground.
- [ ] **Deploy log** — append w21-redesign to `.tmp/tasks/ui-rework/deploys.md`
      (planner-owned, outside this fork's scope).
- [ ] **Deploy worktree cleanup (user confirm)** — `.wt/deploy-redesign` no
      longer needed (image pushed).
- [ ] **(validation fork, parked)** D-13 adoption + 14.9k full-corpus rerun —
      other fork's court.

## Decisions locked with the user

| Decision | Ruling |
|---|---|
| Rollout | **Replace `/runs/:id` in place** (no feature flag, no v2 route) |
| Backend gaps | **Handoff doc written now:** `ui/BACKEND_GAPS.md` (G1–G9, priorities, fallbacks) — hand to backend fork for coordination |
| Phase 0 | Approved and **done** (adapter + fixture tests) |

## Ground docs (read before coding)

- Handoff package: `/home/tomsko/work/bat3_article_reviews/bioid_ui_handoff/` — read order: `README.md` → `SPEC.md` (main spec) → `DATA.md` (view-model contract) → `COPY.md` (verbatim copy); `template/results-page.html` = behavioral reference (**do not copy its HTML/CSS/JS**); `AGENT_BRIEF.md` = phase plan + `@e-infra/design-system` 0.1.9 component map + Mol\* notes + "what not to do".
- `ui/BACKEND_GAPS.md` — gap registry; adapter fallbacks already implement them.

## Phase status

- [x] **Phase 0 — view-model adapter** (commit `4d00efedd`) `ui/src/features/results/viewmodel/`:
  `types.ts` (VM contract), `derive.ts` (names/kind/state/evidence/clauses), `steps.ts` (6-step mapping, warning=done), `notes.ts` (DATA §3 grouping + catalogue), `warningCatalog.ts` (COPY §3 verbatim), `labels.ts`, `adapter.ts` (`adapt(ApiBundle, opts)`), `index.ts` barrel, `fixtures/` (6 handoff JSONs), 5 test files — **71 vitest cases**.
  Implementations of note: G2 status fallback (waiting→searching→searched); G1 name fallback to first input file; G5 additive `name`/`organism` hit fields read defensively; missing verification entry = not_identified; derived not-identified note first; swissprot→"UniProt" label (approved existing copy); `{step}`/`{short_id}` placeholder filling.
- [x] **Phase 2 — molecule list** (commit `3eb0f68b0`) `ui/src/features/results/list/`:
  `moleculeList.ts` pure model (buckets, search/filter, kind groups, identification groups, default selection, injected-storage persistence) + 23 tests incl. SPEC §7 fixture cases; `MoleculeList.tsx` + `DistributionBar.tsx`; `icons.tsx` (custom SVGs for status-medium/low/exact + kind-protein/lipid/unknown, Lucide for the rest); semantic tokens light+dark appended to `index.css` (`--vm-*`, use as `text-(--vm-high)`).
  Not wired into RunResultsPage yet — integration happens when the stage exists (Phase 3).
  Fixture facts learned: NavMs copies are real (SOL ×48,004); identification row ×N = member count; chains are 78.1 (medium), POPC/POPX/SOL 94 (high).
- [x] **Phase 3 — stage** (commits `29233946d` 3a + `7d3aac404` 3b):
  - `stage/`: stageModel (pure: eyebrow/badge/headline/best-line/same-as/FASTA/chem-rows/molecule-notes), AnswerHeader (title + italic subtitle, best-match ↗, same-as link-buttons, confidence badge), StageTabs (Matches table w/ best row, show-all, rejected fold, confidence explainer; Sequence copy/download FASTA; Chemistry dl; per-molecule Notes), Stage (tab remembered across selections when valid). Additive VM fields: `result.evidence`, `molecule.rejected[]` (fixtures valid, optional). 17 tests.
  - `viewer/`: viewerModel (per-KIND components = A6 fix; Highlight/By-confidence; legend; chain↔molecule map; palette from CSS vars) + StageCanvas (create-once plugin kept, watchdog/geometry-preflight/1M-gate/static fallbacks kept; floating controls: mode toggle, water+ions, reset, full-screen; legend pill; camera-kept rebuilds). 8 tests.
  - **G9 gap hit in practice**: `/render` has NO per-segment mmCIF → the `__vN` overlay fallback cannot be built. Chain-addressable molecules only; virtual segments stay neutral base. Documented inline.
  - Not wired into RunResultsPage yet — integration at the page phase.
- [x] **Phase 4 — legacy issue-copy decision** (commit `38a495fa5`): **realigned**, not retired. `signature_generator_failed` floor back to `info` (+skipped-wording) per E-22 `d2e4ca000` + COPY.md §3; the `a7d20a26c` "warning" drift was the outlier. Executor `critical` flag still wins. Suite fully green **212/212** for the first time. WarningsPanel retires when the new page replaces it.
- [x] **Phase 1/5 — run header + error banner + queued state** (commit `d9e761df3`) `header/`: headerModel (pageName/pageTitle/metaLine/actions per SPEC §2, cancel confirm verbatim, bugReport) + RunHeader + ErrorBanner. 8 tests.
- [x] **Phase 4 — status strip + notes pill** (commits `2f917eeec` + `fc65691c4` SPEC-realig): stripModel (leftLine for 4 states, timings line, stepFill w/ molecules_done ratio + indeterminate fallback, facts line, notesPill w/ per-severity counts + lead title, affectsNames hidden until G4) + StatusStrip (slim 6-segment bar, Step-timings ▾ when finished, notes expand with per-note disclosures + Affects chips). 14 tests.
- [x] **Phase 6 — technical fold + page replacement** (commit `dca1d9e43`): **/runs/:id replaced in place**. TechnicalFold (7 entries SPEC §3.6 → existing developer views), whole-run signatures+verification feeding one adapt() VM, selection in ?segment=, tab title per §2, cancel/rerun/cite/download/report wired (runCancel endpoint added). Legacy MolstarViewer/MoleculeSelector/ResultsPanel alive only via dev playground — retire in phase 7.
- [x] **Phase 7 — polish + §7 walkthrough** (commit `24d9d5af2` + wiring):
  - Notes footer "in Technical details" now opens/scrolls the fold (was dead text).
  - §7 checklist status: implemented+unit-tested — 10-row NavMs w/ ions+water collapsed, Chain A default, FASTA copy; 25-row large w/ distribution filter toggle; search "po" expansion; group-by-Identification 5 rows + disabled while running; list/stage-only middle area; pill counts + lead title + fold link; no seg_ outside fold; list→stage 390px order + square canvas; viewer click-select + UNL none-colour; failed banner + red step; queued line.
  - Needs in-browser confirmation after deploy: <15-Tab to first row (static count borderline ~14), dark-theme contrast, 1440×900 header+canvas-top visibility, reduced-motion feel (motion-safe used everywhere).
  - Dev playground (`import.meta.env.DEV`-gated, tree-shaken from prod) still references the legacy stage components → MolstarViewer/MoleculeSelector/ResultsPanel kept alive for it; retiring them = rewrite/remove playground (needs user decision).
  - `deploy/ui-worker.yaml` untouched; deployment still needs user authorization.

## Known issues / incidents

1. **Pre-existing red test (NOT mine, NOT fixed per report-first)**: `ui/src/features/results/utils/issue-copy.test.ts` — expects `signature_generator_failed → "info"`, implementation returns `"warning"` (last touched `a7d20a26c`, warnings v2). Interesting nuance: COPY.md §3 says that code IS info severity — so the old catalog may drift from the redesign copy. Decide at Phase 4 (notes) whether to realign the legacy module or retire it.
2. **Stash incident (2026-10-26, resolved)**: `git stash push` silently skips untracked dirs without `-u`; a blind `pop` then partially applied the OTHER fork's stash@{0} (uniprot_scorer.py WIP, parent 122d1d56d) leaving UU. Restored via `git show HEAD:... > file` + `git reset`. Both foreign stashes intact. **Rule: never `git stash` in this repo — other forks keep WIP stashes here.**

## Hard rules (from handoff "what not to do")

- Copy verbatim from `COPY.md`; no invented thresholds (High≥80/Med 50–79/Low<50) or step labels; never colour-alone confidence (shape icons; custom SVGs only for status-medium/low/exact + kind-protein/lipid/unknown where Lucide lacks them).
- No tabs beyond the 3 molecule tabs; everything dev-facing under Technical details; notes live only in the status strip; list rows = 2 quiet lines, no flags/sizes.
- Fixture placeholders (`[POPE CID]`, `[N] days`, citation text, "30–120 min") must come from config or be hidden — never hard-code.
- Don't assume backend merged identical chains; "Group by: Identification" is UI-side, finished-runs only.

## Verify

```bash
cd ui && npx vitest run src/features/results/viewmodel   # 71 passing
cd ui && npx tsc -b                                       # clean
```

## Open points for the user

1. Backend coordination: pass `ui/BACKEND_GAPS.md` to the API fork (G5 hit names = top UX priority).
2. External write to `/home/tomsko/work/bat3_article_reviews/` is permission-denied for this session — gap doc lives at `ui/BACKEND_GAPS.md`; move it if you want it beside the handoff package.
3. Deployment unchanged (`deploy/ui-worker.yaml`, UI image production-v1) until phases land; user authorizes any image bump.
4. Commits: nothing committed yet in this fork — propose a Phase-0 commit (`viewmodel adapter + fixtures + gap doc`) at next session start.
