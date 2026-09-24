# PLAN — PubChem Local Mirror (formula / CID / InChIKey lookups, zero PUG-REST)

**Status:** planned, not started (created 2026-09-23; legacy reid wave in flight meanwhile)
**Driver:** NCBI dynamic-throttling blacklisted 5 of our 6 known cluster egress IPs on PUG-REST
(2026-09-12 → now; verified 2026-09-23: `X-Throttling-Control: ... too many requests per second
or blacklisted`, instant 503). Verified: **PubChem FTP download is NOT blocked from the cluster**
(`ftp.ncbi.nlm.nih.gov` → 200 from validation-worker pod).
**Goal:** a local, versioned PubChem lookup database — same lifecycle shape as our BLAST DBs —
covering the three lookups we currently buy from PUG-REST:
1. `formula → [CID]` (identify path, `formula_pubchem` resolver)
2. `CID → SMILES / InChIKey / formula / mass` (verification fetch path, `compound_fetcher.py`)
3. `InChIKey → CID` (identity/paranoia checks; future rerank work)

NOT in scope (explicitly): substructure/similarity search, 2D/3D coordinates, name search
(existing name resolvers untouched), PUG replacement for exotic endpoints.

---

## 1. Data sources (live-verified 2026-09-23)

| File | Role | Size (2026-09-22 build) | Notes |
|---|---|---|---|
| `Compound/Extras/CID-SMILES.gz` | CID → isomeric SMILES | **1.49 GB** | tab-separated `CID<TAB>SMILES`, CID-ascending |
| `Compound/Extras/CID-InChI-Key.gz` | CID → InChI(Key) | **7.37 GB** (bigger than est. — likely bundles full InChI; builder must **sniff header rows**, take last InChIKey-shaped column) | CID-ascending |
| `Compound/Extras/CID-Mass.gz` | (fallback) exact mass | 1.39 GB | only if RDKit-derive fails sanity |
| `Compound/Extras/CID-IUPAC.gz` / `CID-Title.gz` | (optional) names | 1.85 / 1.89 GB | skipped for v1 |
| `*.md5` sidecars | integrity | 48 B | download + verify each |

Base URL: `https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/`
**`CID-Formula.gz` does NOT exist (404, verified)** — molecular formula must be *derived from
SMILES with RDKit at index time* (Hill ordering, same convention PubChem uses).
Update cadence upstream: rolling (roughly weekly). Our sync: weekly, md5-driven (skip when unchanged).
License: PubChem data ≈ public domain; keep a `SOURCES.md` with URLs + fetch date + attribution.

## 2. Architecture

Layout follows the established BLAST-DB pattern (staging dir → build → validate → atomic symlink swap):

```
/app/databases/pubchem/                    # on PVC bat3-bat3-databases-data
├── staging-20260923-1200/                 # in-flight build (pod-kill-safe: resumable)
├── v2026-09-23/                           # completed version
│   ├── pubchem.sqlite                     # the DB
│   ├── build_metadata.json                # sources, md5s, row counts, timings, git sha
│   └── raw/                               # optional retained .gz (behind --keep-raw flag)
├── staging-*/                             # cleaned on success
└── current -> v2026-09-23                 # symlink flip = activation; flip back = rollback
```

### SQLite schema (chosen engine — rationale in §7)

```sql
CREATE TABLE compounds (
    cid          INTEGER PRIMARY KEY,           -- PubChem CID
    smiles       TEXT NOT NULL,                 -- isomeric SMILES (as published)
    inchikey     TEXT,                          -- 27-char, from CID-InChI-Key.gz
    formula_hill TEXT NOT NULL,                 -- derived via RDKit, Hill order
    exact_mass   REAL                           -- derived via RDKit (monoisotopic)
);
CREATE INDEX idx_formula  ON compounds(formula_hill);
CREATE UNIQUE INDEX idx_inchikey ON compounds(inchikey);
-- build pragmas: journal_mode=OFF, synchronous=OFF, page_size=32768; ANALYZE after.
```

Query mapping:
- `formula → CIDs`: `SELECT cid FROM compounds WHERE formula_hill = ? ORDER BY cid LIMIT ?`
  (matches PUG `MaxRecords` ascending-CID semantics — Phase 0 contract check)
- `CID → row`: PK lookup
- `InChIKey → CID`: unique-index lookup
- missing locally → soft-fail to next resolver/fetcher (PUG-via-proxy, eutils, ChEMBL)

Estimated final size: ~25–40 GB including indexes (~120M rows). RAM during build: bounded
(streaming, 1M-row batches). Build host: k8s Job using the worker image (RDKit included).

## 3. Phases & tasks

### Phase 0 — Recon & capacity gate (~30 min) 🚪  ✅ DONE 2026-09-24
- [x] HEAD each Extras file → sizes recorded in §1 (InChI-Key file is 7.37 GB, format sniff required)
- [x] `df -h` on databases PVC → **70 TB free** — passes
- [x] Contract audit → §8 (all PUG call sites enumerated, incl. **hfamily** which the
      first draft missed)
- [ ] Hill convention → deferred to Phase 3 golden fixture (parity asserts it automatically)

**Gate: PASSED → Phase 1 cleared.**

### Phase 1 — Populate script + k8s Job (2–3 h)
- [ ] `scripts/populate_pubchem_mirror.py` — modeled on `populate_blast_databases.py`:
      manifest-driven (URLs from §1), retries + `Retry-After` etiquette, size+md5 verification,
      staging dir `staging-<ts>`, skip-already-verified files on retry (resumable),
      `--keep-raw`, `--limit N` (sample builds), `--target-dir`.
- [ ] `k8s/pubchem-mirror-build-job.yaml` — modeled on `blast-db-download-job.yaml`
      (worker image, databases PVC at `/app/databases`), higher limits
      (requests 4 CPU/8Gi, limits 8 CPU/32Gi), `activeDeadlineSeconds: 86400`, `backoffLimit: 2`.
- [ ] Extend `scripts/download-databases.sh` with a `--pubchem` (or `pubchem`) subcommand.
- [ ] Extend `scripts/validate_databases.py` (or sibling `validate_pubchem_mirror.py`):
      file presence, sqlite integrity (`PRAGMA integrity_check` on sample pages), row-count
      sanity vs metadata, symlink points at a valid version.

### Phase 2 — Index build machinery (3–5 h)
- [ ] `src_new/chemistry/pubchem_db.py`:
  - `build(db_path, smiles_gz, inchikey_gz, limit=None)` — zip-merge the two CID-ascending
    streams (assert monotonic; tolerate rows missing on one side, count them).
  - RDKit per row: `MolFromSmiles` → `CalcMolFormula` (Hill) + `ExactMolWt`; parse failures
    counted, first 50 logged, never fatal. Multiprocessing (chunks of 100k, `imap unordered`
    only within batch; CID order restored by sort on flush — or simpler: derive in worker
    processes, single writer process inserting in batch order).
  - Batched `executemany` (1M/txn), commit-checkpoint marker file every 5M rows →
    **resumable after pod kill** (mandatory; cf. pod-OOM/no-hup session files lesson).
  - Indexes + `ANALYZE` post-load; final `PRAGMA optimize`; write `build_metadata.json`.
  - Read API: `class PubChemDB: by_cid(cid) -> Row|None; by_inchikey(ik) -> cid|None;
    by_formula(hill, limit=10) -> list[int]`; open with `mode=ro&immutable=1`,
    per-process connection (no shared handles across fork).
- [ ] Config knobs: `[pubchem] local_db_path = /app/databases/pubchem/current/pubchem.sqlite`.
- [ ] Full build run on the Job; benchmark gate (from a validation-worker pod, cold + warm):
      `by_cid` p95 < 20 ms warm; `by_formula('C6H12O6')` p95 < 150 ms over NFS; else report
      before integrating (NFS fallback: optional node-local copy step — decide only with data).

### Phase 3 — Small-sample + parity tests (1–2 h)
- [ ] `--limit 2000000` mini-build end-to-end (proves pipeline in minutes, not hours).
- [ ] Golden parity fixture (capture on workstation where PUG is clean):
      `tests/fixtures/pubchem_golden.jsonl` — 50 formulas (water, ethanol, ATP, heme,
      camphors, metal complexes, salts with components, an absurd formula → `[]`),
      20 InChIKeys, 20 CIDs, each with captured PUG response. Assert set-equality vs local DB
      (order-insensitive; limit semantics per contract). **Any systematic mismatch →
      §8 contract doc updated + decision recorded; never silently patched.**
- [ ] `tests/src_new/chemistry/test_pubchem_db.py` — synthetic 20-row fixture DB built in tmp,
      no network, no NFS; covers build edge cases (bad SMILES, missing inchikey, limit semantics).
- [ ] `scripts/pubchem_lookup.py --formula C2H6O | --cid 702 | --inchikey ...` ops CLI
      (the debugging tool we wished we had during the audit).

### Phase 4 — BAT3 integration (3–4 h)
- [ ] `src_new/identification/resolvers/formula_local.py` — `FormulaLocalResolver`
      (`name = formula_pubchem_local`, `identifier_type = PUBCHEM_CID`); registered **before**
      `formula_pubchem` in `identification/registry.py`; gated on `[identifiers] formula_local`
      (default **yes**, auto-degrade to PUG chain with one WARN line if DB file missing).
- [ ] `src_new/identification/resolvers/hfamily.py` — swap its PUG fastformula call to
      `by_formula` with local-first fallback (audit found this second formula consumer).
- [ ] `verification/fetchers/compound_fetcher.py` — for CID and INCHIKEY fetch paths:
      local DB first; PUG/eutils only on local miss or DB absent; when mirror present,
      `VALIDATION_SKIP_PUG=1` becomes fully offline; IDSM/cactus fallback chains can retire
      for CID/InChIKey (keep code, demote below local).
- [ ] Update `tests/src_new/identification/test_offline_fallbacks.py` (registration order,
      degrade path); add fetcher local-first tests.
- [ ] Proof gate (same discipline as v2.33 fallbacks): 3 campaign entries
      (top-10 entry, worst entry, median entry) → candidates present, verified rows with
      expected conf; then config: `/data/validation/config_shared.ini` gets
      `formula_local: yes` + `local_db_path`; rollout via usual build-push-confirm cycle
      (images `v2.34`/`v3.115`).
- [ ] Success metric recorded: PUG-REST calls per completed entry → ~0 for formula+CID paths
      (log counter or grep `pug` in worker logs over 1 h).

### Phase 5 — Ops, lifecycle, docs (1 h)
- [ ] Weekly CronJob `bat3-pubchem-mirror-sync` (md5-driven: no-change → exit 0 in seconds;
      change → full Phase-1/2 rebuild on a new version dir, symlink flip on success).
  Keep last 2 versions, prune older (guard: never prune `current`).
- [ ] Rollback runbook section: `ln -sfn <prev> current` + smoke query.
- [ ] Docs: `docs/PUBCHEM_DATABASE.md` (mirror of `BLAST_DATABASES.md` structure),
      link from `docs/CHEMISTRY_FIX_TODO.md` + `VALIDATION_RERUN_PLAYBOOK.md`,
      incident-registry addendum ("PUG dependence eliminated for formula/CID paths").
- [ ] Commit in two logical commits: machinery+tests, then integration+config docs.

## 4. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Upstream renames/changes Extras format | manifest + header sniffing; fail loud; md5/size recorded in metadata |
| Build pod killed mid-run (known class) | checkpoint markers every 5M rows; staging dir resumable; Job `backoffLimit` |
| RDKit formula ≠ PubChem formula (components, charges, isotopes) | Phase-0 convention check + golden parity fixture; document deltas, never patch silently |
| NFS read latency hurts verifier | immutable read-only DB (page-cache friendly); benchmark gate in Phase 2 before integration |
| PVC capacity (25–40 GB new) | Phase-0 80 GB-free gate |
| `LIMIT 10` semantics differ from PUG (we lose recall) | contract audit; parity fixture asserts top-N equality on live samples |
| Forked processes sharing sqlite handle | per-process open (`uri ro, immutable=1`), enforced in `PubChemDB.__init__` |

## 5. Effort & footprint

- Total: **~1 focused day** (P0 0.5h + P1 2.5h + P2 4h + P3 1.5h + P4 3.5h + P5 1h, overlapping).
- Disk: ~13 GB raw .gz retained per version + ~35 GB DB per version, 2 versions kept → reserve ~100 GB (we have 70 TB).
- One-time build: ~1–2 h CPU (8 cores) download+index. Weekly sync: seconds when unchanged.

## 6. Alternatives considered (rejected)

| Option | Why not |
|---|---|
| Full SDF dump + own index | ~500 GB + huge parse cost; gives coordinates we never use |
| PubChemRDF/SPARQL self-host | infra overkill; IDSM SPARQL already proved thin for chemistry |
| DuckDB/parquet | great for scans, weaker for single-row point lookups + new dep; SQLite wins on simplicity & zero deps |
| LMDB/KV store | fine, but SQL gives us free filtering/limits and everyone can debug it |
| eutils-only | stay remote + 10 r/s cap still throttles burst; keep as fallback not foundation |

## 7. Open questions

- [x] Fields consumed by verification → §8: **SMILES text only** (per identifier). No mass,
      formula, or synonym fields read from PUG anywhere in the fetch path.
- [ ] PUG `cids/txt|json` ordering + implicit caps → pinned by the Phase 3 golden fixture
      (`by_formula` uses `ORDER BY cid LIMIT n`; fixture must include one huge formula).
- [x] Keep raw .gz per version → **yes** (~13 GB; provenance + rebuild without re-download).
- [x] Timing → build integrates against wave in background; integration image rolls only
      when safe (deploy freeze lifted 2026-09-24 for celery fix; mirror image will ride the
      same rule — roll only between dispatch batches, or with `VALIDATION_DISPATCH_ENABLED=0`).

## 8. Contract notes — PUG consumption map (audited 2026-09-24)

### Call sites that hit `pubchem.ncbi.nlm.nih.gov/rest/pug`

| # | File | Endpoint | Purpose | Mirror covers? |
|---|---|---|---|---|
| 1 | `identification/resolvers/formula.py:200` | `fastformula/{f}/cids/txt` | identify: formula→CIDs | ✅ `by_formula` |
| 2 | `identification/resolvers/hfamily.py:143` | `fastformula/{f}/cids/JSON?MaxRecords=N` | identify: H-family neighbor formulas (e.g. ±H around `C25H18N4O5`) | ✅ `by_formula` (same query; add resolver task to Phase 4!) |
| 3 | `identification/resolvers/pubchem.py:193` | `smiles/cids/txt` | identify: fastidentity SMILES→CID | ⚠️ v1 no (needs fastidentity semantics, not string match; InChIKey covers most identity needs) |
| 4 | `identification/resolvers/pubchem.py:285` | `fastsimilarity_2d/{s}/cids/txt?Threshold=` | identify: similarity candidate generation | ❌ **never in v1** (needs fingerprints; stays remote-by-design, low QPS → future PUG-via-proxy funnel) |
| 5 | `identification/resolvers/inchikey.py:229` | `inchikey/{ik}/cids/txt` | identify: InChIKey(+variants)→CID | ✅ exact `by_inchikey`; variant queries stay remote (low volume) |
| 6 | `verification/fetchers/compound_fetcher.py` (`_fetch_pubchem`, `prefetch_pubchem`) | `cid/{cids}/property/CanonicalSMILES` (+TXT) | verify: CID→SMILES | ✅ `by_cid`; IDSM-fallback path retires |
| 7 | same, `_fetch_inchikey` | `inchikey/{ik}/property/CanonicalSMILES` (cactus first, PUG last-resort) | verify: InChIKey→SMILES | ✅ direct `by_inchikey`→smiles (cactus fallback retired) |

### Fetch-path facts
- Verification reads **only SMILES strings** back from any source; nothing else consumed.
- PUG `CanonicalSMILES` == current `ConnectivitySMILES`; `CID-SMILES.gz` publishes the
  **isomeric** SMILES — superset information. Golden fixture must document any consumer
  that assumed connectivity-only semantics (skeletize is stereo-insensitive by design).
- Soft-fail semantics to preserve: `404/400 → []/None`; transport errors raise fail-soft
  upstream (`IdentifierResolutionError` logged as attempt). Local DB miss ≡ 404.
- `MaxRecords` values seen: 200 (hfamily `_MAX_RECORDS_PER_QUERY`), none elsewhere.

---

**Next action when resumed:** run Phase 0 (30 min checklist), report gate result, then Phase 1.
Related: `docs/CHEMISTRY_FIX_TODO.md` (inchikey verdict), playbook §5b (replay mechanics),
commit `cf4e22bfb` (context for PUG blacklist evidence).
