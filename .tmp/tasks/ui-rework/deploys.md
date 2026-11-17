# Deploy Log — UI Rework

## 2026-10-01 W1 skeleton smoke deploy ✅
- Image: cerit.io/tomsko/bat3-frontend:next (digest sha256:822cac967b7d) → deployment bat3-ceitec-bat3-web
- Backups: registry bat3-frontend:legacy-pre-rework (d60c7d983e1f), backups/bat3-web-deploy-pre-rework.yaml, backups/ingress-pre-rework.yaml
- Rollback: kubectl set image deployment/bat3-ceitec-bat3-web web=cerit.io/tomsko/bat3-frontend:legacy-pre-rework -n ceitec-biodata-ns (or rollout undo)
- Smoke results:
  - / → new SPA (data-theme=custom, fresh hashed assets) ✅
  - asset JS 200 ✅ · /health → API ✅
  - /api/v1 → 404 from FastAPI = nginx /api proxy chain works, awaits API deploy ✅ (expected)
  - deep-link /runs/<id> → still JSON (KNOWN, WS7 ingress fix pending) ✅ tracked

## 2026-10-01 A-wave2 API deploy ✅ (gate: PASSED, independently verified)
- Gate: pytest 62 passed + 2 pre-existing failures (VERIFIED pre-existing at f8d78423a worktree - NOT caused by A2 or F16; logged to PLAN known-issues). OpenAPI diff: 0 removed paths/methods, +23 additive (`/api/v1/*` aliases + `/runs/{id}/queue` + `/runs/{id}/rerun`).
- Image: cerit.io/tomsko/bat3-api:ui-rework-a2 (sha256:f9c73f44fc73) → deployment bat3-ceitec-bat3-api. Backup: backups/bat3-api-deploy-pre-a2.yaml; rollback image tag: ui1.
- Live smoke: /api/v1/health 200 ✅ · /api/v1/runs list ✅ · legacy /runs 200 ✅ · ?mine=1 200 ✅ · rerun fake-id → clean 404 ✅ · queue finished-run → done ✅ · **links: 1,600 RCSB URLs on bce4a0fa, broken_suffix=0** ✅
- Fixtures identifiers/verification for bce4a0fa refreshed to post-fix truth.
- Live now: /api/v1 alias, creator_ip on new runs, ?mine=1, /runs/{id}/rerun, /runs/{id}/queue, canonical database_url.

## 2026-10-01 W2 frontpage deploy ✅
- Image: cerit.io/tomsko/bat3-frontend:w2 (sha256:d1aa8440f1f1) ← built from CLEAN WORKTREE at ac00189eb (worktree builds are mandatory since .gitignore-collision incident)
- Live: frontpage upload flow (dropzone, config dialog, fast mode, run name) + IP-bound recents (mine=1) + rerun/delete dialogs. Results page: still stub (B-wave pending).
- E2E smoke run: POST /api/v1/runs 1CRN.pdb → run 89fe2c7b-8c2c-426a-9f02-a235b74232e7, success <10s, type_counts {protein:1}; ?mine=1 returned exactly 1 (IP binding works); queue state transitions queued→running observed.
- KNOWN remaining: deep-link /runs/<id> direct-entry → JSON (WS7 ingress fix, next infra wave).

## 2026-10-01 W3 theme + B-wave1 components deploy ✅
- 746a782e1 green theme: setup.css :root is UNLAYERED purple → DS custom_setup (layered) can never win. Fix: unlayered html[data-theme=custom] full token override (brand, ramps 50-950, heading, focus, charts) - beats :root by specificity, cascade-proof.
- 6708cc453 lint gate fixes (B-wave1 now lint/typecheck/test/build all green, 86 tests).
- Image bat3-frontend:w3 (sha256:e9d91f5b26e1) from clean worktree 6708cc453. Live css verified: #2e7d32 present, data-theme=custom in bundle.
- Includes B-wave1 components (TaskBar, MoleculeSelector, ResultsPanel, SignatureDialog, utils) - not page-wired yet; B-wave2 (integration, adaptive polling) running now.

## 2026-10-01 W4 full results UI deploy ✅ (B-wave2 gated: 86 tests, lint/typecheck/build green)
- Session resilience note: network reset killed b-wave2 at D3; resumed detached from D3->D5 clean (insurance architecture held).
- Commits: d957b4767 hooks (adaptive polling), b85339cba page assembly, 8162fc26d warnings panel+catalog copy, 8978e166e tabs, 9277b37c8 molstar single-plugin + 25s watchdog -> static PNG fallback -> gray "Structural data not available".
- Image bat3-frontend:w4 (sha256:e42cb9f7e986) from clean worktree 9277b37c8. Bundle smoke: results UI strings present.
- Remaining: WS7 ingress deep-link fix; then 4-run visual suite with user.

## 2026-10-01 WS7 deep-link fix + w5 deploy ✅ BUG KILLED
- Cause chain: ingress /runs->api AND nginx-frontend /runs->api. Fix both: ingress now /api,/files,/health,/docs,/openapi.json -> api, / -> web; nginx-frontend reduced to SPA fallback + /api + /files proxies.
- Applied: ingress-ws7-fixed.yaml (backup of old: backups/ingress-pre-rework.yaml). Chart template updated for posterity (bat3-chart/templates/ingress.yaml).
- Image bat3-frontend:w5 (sha256:89405826231d).
- Matrix: /runs/<id> 200 text/html (was JSON) | /api/v1/* JSON | /health JSON | /openapi.json JSON | / HTML. API surface at host root is GONE by design (SPA routes); clients use /api/v1.
- Rollback: re-apply backups/ingress-pre-rework.yaml + set web image bat3-frontend:legacy-pre-rework (nginx conf inside image matches old behavior).

## 2026-10-01 B1 fix-forward wave deployed ✅ (api ui-rework-b1 + ui w6)
- All 6 groups: header fallback+uuid, taskbar, molstar context (0.02 + element colors), swissprot/inchikey links (API+UI), loading/input/files correctness, warnings v2 (info demotion + humanized resolvers + sanitized technical detail). Bonus: rules-of-hooks crash-risk fix. Tests: 98/98.
- Live verified: SWISSPROT 6/6 uniprot links; INCHIKEY pubchem-query link; deep-link 200; site 200.
- INCIDENT 2026-10-01 (~2min site down): masked exit codes via `| tail` chains let kubectl set image to nonexistent :w6 -> ImagePullBackOff w/ Recreate strategy. Rolled back to w5 immediately. LESSONS (now enforced): (1) set -o pipefail in deploy chains, (2) pre-flight docker image inspect before set image, (3) worktree stale registrations cleaned via prune/remove, (4) rollout timeout => immediate rollback check. Also: agent session death #4 (15min in); G5+G6 finished by planner from disk salvage.
2026-10-01 W7: ResultsPanel table scroll-capped 420px + sticky header (cd832cb50). Clean hardened deploy (pipefail + preflight image inspect).

## 2026-10-01 CUTOVER — ui-production-v1 ✅
- 4-run data+page matrix: 100% green. User matrix sign-off received.
- Retag bat3-frontend:w8 -> bat3-frontend:production-v1 (same digest - provenance-stable deploy), rolled out.
- git tag ui-production-v1. This concludes the rework; fix-forward treated as new waves on this base.
- Living docs: PLAN.md (status + backlog), errors/error-catalog.json (warning copy source of truth), contracts/ (openapi baselines), fixtures/ (response snapshots), backups/ (pre-rework yamls + rollback pointers).
2026-10-01 W9: right panel absolute inset-0 bound to left column height incl. table scroll (40b88fbf5); production-v1 retagged to w9 digest.
2026-10-01 W10: name/identifier merged column deployed (production-v1 -> w10 digest).
2026-10-01 W11: Verification tab merged column parity (was the table user still saw two columns in). production-v1 -> w11.


## 2026-10-02 W12 truthing deploy + panel merge ACTUALLY live
- P2-7 discovered: production-v1 same-string set-image no-op'd w10+w11 rollouts; pod served w9 for ~1 day. User report (two columns) led to root cause via html-asset-hash parity check.
- State now: tab reverted to two-column (ba7b9921f, user preference), panel merged. w12 digest == w10 digest f810a51e (ui/ byte-identical to w10 worktree - reproducibility confirmed).
- Deploy discipline updated: unique tags trigger rollouts; production-v1 = registry pointer only; html-asset-hash parity = standard post-deploy verification.

## 2026-10-02: UI rework formally CLOSED. All waves + fix-forwards live & verified; topic archived.

## 2026-10-26 w21-redesign (backfilled 2026-11-06)
- /runs/:id redesign live: cerit.io/tomsko/bat3-frontend:w21-redesign, built from clean worktree @ 24d9d5af2 (UI fork report). Rollback = set image back to w20.

## 2026-11-06 w22-viewerfix + w23-cachefix ✅
- w22 (1a1a929f4, sha256:f6d8165e): 3D viewer never rendered on w21 — MVS scene used colour {hex}, water "point", selector "non_standard" (all invalid MVS → whole scene rejected, "Structural data not available"). buildMvs extracted to viewer/mvsScene.ts, typed against molstar MVS; regression test validates every scene with MVSData.validationIssues(noExtra). Header input line shows input/ files only (was the whole run dir).
- w23 (782600844, sha256:e27d2301): nginx Cache-Control — `no-cache` on the HTML shell, `public, max-age=31536000, immutable` on /assets/ (=404 for missing chunks). Root cause found during w22 verification: no Cache-Control → heuristic caching of index.html → browsers kept the old bundle after rollout (likely also the 10-02 "rollout did not take" class).
- Verified: pod digest e27d2301, HTML `cache-control: no-cache` + index-BE-pEx9t.js, asset immutable header, missing asset 404, /api/v1/capabilities 200; browser: viewer renders, 0 console errors.
- Acceptance (handoff TODO 1): Tab to first molecule row = 14 (<15) ✓, 1440×900 header ✓, reduced motion ✓ (no animations), dark theme unreachable (nothing sets html.dark) and incomplete if forced (21 WCAG failures) — not shipped.
- Snapshot: backups/bat3-ceitec-bat3-web.pre-w22.yaml (rollback: set image web=cerit.io/tomsko/bat3-frontend:w21-redesign).

## 2026-11-06 w24-system + w25-g9 (frontend), b26 (API + fleet workers + ui-worker) ✅
- w24 (5fa0807b3, sha256:c173d979): whole-system view (list button + SystemStage, ?segment=__system__, canvas opens by confidence).
- b26 (f93a29883, sha256:1dd24de9) on bat3-ceitec-bat3-api, bat3-ceitec-bat3-worker AND bat3-ui-worker: export keeps insertion codes (3PTB system mmCIF failed), O-only crystal water verifies as water (CID 962), virtual segment display_name = resname. API env BAT3_TYPICAL_DURATION_MIN=2/MAX=8 (G8, g1 p10–p90).
- FINDING: API/UI-submitted runs execute on `bat3-ui-worker` (queue validation.ui.celery), which had stayed on b13-era sha256:5a79ef4f (git-c8135d10c). Every image rollout must include it.
- w25 (573b3981c, sha256:2fe4e36c): G9 selector colouring (chain / selector chain / atom_index), long-name safety (line-clamp, wrap-anywhere, tooltips), legacy MolstarViewer/MoleculeSelector/ResultsPanel + DEV playground removed.
- Verified on API run 79ba82ce (3PTB, b26 ui-worker): system.mmcif + selectors present, water PubChem 962 conf 100, names BEN/CA/HOH.
- Snapshots: rollout_b24/*.pre-b26.yaml (bioid_bughunt), backups/bat3-ceitec-bat3-web.pre-w22.yaml.

## 2026-11-06 b28/b29 + w26–w28 ✅
- b28 (82d9c0879, sha256:347f13db): G9 selectors cover ALL copies + residue_ranges; ligand names (mirror IUPAC / element names, read-time backfill). b29 (4877b492e, sha256:07c0aabb): names capitalized. Released to API + fleet + ui-worker via bioid_bughunt/rollout_b24/release.sh (refuses on queued/active work; snapshots every deployment).
- w26 (sha256:db8a1075): UI residue ranges first. w27 (afaf85185): each molecule drawn once — BLANK canvas in prod → rolled back to w26 within minutes. w28 (e8940b8db, sha256:779b47a9): the real cause — StageCanvas loaded each MVS scene twice concurrently; fixed; verified on a local production build + live (TARP+145 POPC, 3PTB fully coloured).
- Fleet bat3-ceitec-bat3-worker scaled 200 → 8 (user: no large re-eval today).

## 2026-11-06/07 b30–b34 + w29 (g1 bughunt close-out) ✅
- b30 (971de6235): free nucleotides are ligands (901 g1 re-runs). b31 (5f0efbaa7, sha256:1505b80f): a lone whole residue is a monomer ligand, never a chain (+ bond-distance safety net; 575 re-runs, corpus probe 575 changed / 14,498 identical). b32 (6bcfeadfe, sha256:ca28ee39): tiny segments signatured first + one-residue mmCIF payload skipped (67 re-runs). b33 (497395c0c, sha256:451b5c23): smallest segments verified first (177 re-runs incl. 162 pre-b26 export failures). b34 (dc9de0edb, sha256:b0c4a4cc): display names only — PubChem titles (new optional file /app/databases/pubchem/current/pubchem_titles.sqlite, 124.9M rows from CID-Title 2026-11-06, mirror untouched) and PDB entity descriptions for the top PDB hits. All via bioid_bughunt/rollout_b24/release.sh (API + fleet + ui-worker; snapshots *.pre-<stamp>.yaml).
- w29 (c4767052f, sha256:3646b342): notes hide declared not-applicable outcomes (no_polymer_payload, na_mode_unsupported) and box-less pbc_unwrap_failed; asset hash parity verified (index-BSrGjvPC.js). Rollback: rollout_b24/bat3-ceitec-bat3-web.pre-w29.yaml.
- Fleet bat3-ceitec-bat3-worker scaled 24 → 8 after the campaign (snapshot rollout_b24/bat3-ceitec-bat3-worker.pre-scaledown-8.yaml).

## 2026-11-09 b36 + w30 + w31 (UI audit fixes) ✅
- b36 (29a022ae5, sha256:dd8151d7) via release.sh to API + fleet + ui-worker: GZip on the API (system.mmcif 22 MB → 3.7 MB on the wire), system export keeps molecules in their input periodic image (3PTB benzamidine back in the S1 pocket, 2.82 A from the protein), one-atom hits named as ions ("Chloride"). Also carries 610bb59ab (pod-local resolver cache wins over run config). 3PTB rerun identical to b34 (P00760 84.1 top, 100 verified).
- w30-audit (29a022ae5, sha256:e3b0e499), then w31-live (9a95da063, sha256:ce4e3c90, index-BEuc1sPR.js): audit batches 7ac3a6996 / eae09e097 / f19793fda / 29a022ae5 / e6f8a73ee / 9a95da063 — honest failed/cancelled states, CSV + typical duration from /capabilities, labels, phone stage header, Mol* toolbar hidden, a11y (axe 0 on audited pages), Recents sorted, upload validation, config dialog, 404 route, nginx gzip + Mol* lazy-loaded (front page JS 5.4 → 0.62 MB), "Title>Description" run names, refetch error no longer shows "Run not found", live rows follow per_segment progress.
- Rollback: web → rollout_b24/bat3-ceitec-bat3-web.pre-w31.yaml (w30) or pre-<stamp>.yaml (w29); backend → rollout_b24/*.pre-<stamp>.yaml (b34 sha256:b0c4a4cc).

## 2026-11-09 b37 + w33 ✅
- b37 (de7f8d1f9, sha256:ae8df43f) via release.sh: every verified PDB hit named after its matched entity (fail-safe: 8 s/no-retry uncached lookups, ≤12 entities, 30 s/segment, 180 s/run, ≤¼ of remaining verify budget above 60 s, stop after 3 failures); config.ini BLAST timeout_s 300 → 3600 (UI runs only; config_shared.ini keeps 600); reruns record requester IP, "Title (re-run)>Desc".
- bat3-ui-worker env VALIDATION_STAGE_BUDGETS={"identify_molecules": 4500} (fleet untouched).
- w33-seq (de7f8d1f9, sha256:b34dc4df): nucleic acids show their sequence (fasta_map_nucleic).
- Earlier same day: w32-finish (efce1eca7, sha256:184ad513), API env BAT3_EXAMPLE_RUNS = 1c2a4d4b / 8338ea32 / 6b21b4ec (curated landing examples).

## b38 / w34-supdb — supplementary databases (2026-11-09)
- Backend `cerit.io/tomsko/bat3-validation-api@sha256:9f6b817053a7450fc74e12565c270335030c3a418159b4b2eb8f33f4d6ea70cc` (git ad7f91f95) on API, fleet worker (8/8), ui-worker; web `bat3-frontend:w34-supdb` (`sha256:924c9d2b…`). release.sh, snapshots in rollout_b24/*.pre-<stamp>.yaml.
- New data (new paths only): `/app/databases/uniref50` -> `.staging/uniref50-20261109-113411` (41,243,524 seqs, UniRef50 2026-11-04); `/app/databases/foldseek/pdb*` (pdb100, PDB_DATE 250101); `/app/databases/{sifts,swisslipids,chebi}/*.sqlite`. Jobs: k8s/uniref50-blastdb-job.yaml, k8s/foldseek-pdb-db-job.yaml, k8s/reference-indexes-job.yaml.
- Enabled in config.ini only (UI runs); eval configs (/data/validation/config_g1.ini, config_shared.ini) name none of the keys -> off. Plan: .tmp/tasks/new-databases/PLAN.md.
- Before/after: C07 free ATP 86c1592b -> 1df31cc7: additive, top unchanged, +3 ChEBI.
- b39 (2134ec8d0): slow NCBI searches deferred to the end of the second pass. b40 (792d04669, `sha256:61722e6a…`): their evidence verified after the regular window (verify_top_n_supplementary 40).
- 2026-11-09 16:14 UTC: bat3-ui-worker scaled 2 -> 10 replicas on user request (snapshot rollout_b24/bat3-ui-worker.pre-scale10-*.yaml); all on b40, consuming validation.ui.celery.
- Before/after (compare.py: nothing previously verified lost, no confidence drop): C07 ATP 86c1592b->1df31cc7 additive (+3 ChEBI); P04 3PTB 5ee8666f->91a997fa additive (+20 PDB; top 1AQ7 81.4 -> P00760 92.1 via SIFTS); M02 E-protein membrane 8338ea32->8aecbc66 additive (POPC +SLM:000000651 +CHEBI:73001; protein +67 nr); M01 protein-DNA 6b21b4ec->fb5009a2 on b40 additive (+40 protein, DNA +12 PDB; b38/b39 runs 2aad52dc/032d9704 were not: nr budget starvation, then nr taking window slots — fixed by b39/b40).
