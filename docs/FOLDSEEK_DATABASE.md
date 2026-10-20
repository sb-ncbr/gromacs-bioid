# Foldseek Database Guide

**Purpose:** Reference documentation for foldseek database management and resolver modes in bat3

**Last Updated:** 2026-10-20 (v3.138 wave)

---

## What foldseek does here

The `foldseek_3di` identification resolver searches protein **structures** (the `ca_only_pdb` signature — a CA-trace PDB) against an AlphaFold database and emits `UNIPROT_ID` candidates. Hits are verified independently by the structure worker with a real TM-score (`tmtools.tm_align`) against the AFDB model fetched by the structure fetcher.

Key architectural fact (empirically established 2026-10-20, foldseek `9-427df8a`):
**foldseek consumes structure input, not 3Di letter strings.** `foldseek createdb` on a FASTA fails with *"No structures found in given input"* — its 3Di encoding is computed internally from the structure. CA-only PDBs work fine and yield hits identical to full-atom PDBs. The old `3di_sequence` signature is not consumed by any resolver (the `tdi.py` generator is independently defective — arg-order + digit-encoding; fix-or-retire is ledgered as TODO in `.opencode/context/bat3/lookup/status.md`).

---

## Execution modes (`[foldseek]` section in `config.ini`)

```ini
[foldseek]
mode = local                                   ; local | remote | off
db_path = /app/databases/foldseek/swissprot   ; local DB prefix
remote_url = https://search.foldseek.com/api
remote_database = afdb-swissprot
remote_polls = 12
; remote_poll_interval_s = 5.0
; remote_timeout_s = 10.0
; max_target_hits = 20
; search_timeout_s = 300
; foldseek_exec = foldseek
```

| Mode | Behavior |
|------|----------|
| `local` (default) | `createdb(structure) → search → convertalis` against `db_path`; **falls back to remote** on missing binary, missing DB, or any local-stage failure |
| `remote` | Public server only (structure POST, `mode=3diaa`, `database[]=<remote_database>`) |
| `off` | Resolver disabled |

Both modes normalize targets `AF-<ACC>-F1-model_vN` → bare accession, so local-DB and server identifier spaces agree (local DB entries may carry older model versions than the server's — normalization absorbs this).

---

## Local database

- Content: `foldseek databases Alphafold/Swiss-Prot <prefix> <tmpDir>`
- Location (ceitec): `/app/databases/foldseek/swissprot*` on PVC `bat3-databases-data-ceitec` (~1 GB at 2026-10)
- Seed/refresh: `k8s/foldseek-db-seed-job.yaml` — run digest-pinned, then delete + re-apply to refresh
- Binary: static release `9-427df8a` (avx2 + sse2 layers via `scripts/docker/foldseek-wrapper.sh` ISA dispatch); image build gates `foldseek version` and `curl --version` (`databases` shells out to a downloader)

### Refresh / re-seed

```bash
kubectl -n ceitec-biodata-ns delete job bat3-foldseek-db-seed-v3138c
kubectl -n ceitec-biodata-ns apply -f k8s/foldseek-db-seed-job.yaml
kubectl -n ceitec-biodata-ns wait --for=condition=complete job/bat3-foldseek-db-seed-v3138c --timeout=45m
```

### Verify from a worker pod

```bash
kubectl -n ceitec-biodata-ns exec deploy/bat3-ceitec-bat3-worker -- sh -c \
  'ls /app/databases/foldseek/swissprot* | head; foldseek version'
```

---

## Troubleshooting (all observed live, 2026-10-20)

| Symptom | Cause | Fix |
|---|---|---|
| Job `BackoffLimitExceeded`, pods gone, no logs | `foldseek databases` requires curl/wget/aria2c; slim image has none | v3.138 installs curl; repro commands in local docker before re-running Jobs |
| Same failure after image rebuild/push | Job uses `repo:tag` + IfNotPresent → node image cache serves the OLD tag | pin Job/deployment images by `@sha256:` digest |
| resolver silent / zero candidate hits | binary probe used `--version` flag (rc=1; subcommand is `version`) | fixed in v3.138 availability check |
| "No structures found in given input" | `createdb` given a FASTA — structures only | resolver feeds `ca_only_pdb` structure text |
| local search rc=0 but no `.m8` | `--format-output` is a `convertalis` flag, not `search` | `search → convertalis` two-step |
| remote returns alignments but parser yields nothing | payload is nested per query; `seqId` is percent-scale on current server | parser flattens one level + normalizes 0..1 vs 0..100 |
| TM-score was always the sequence proxy | `from tmtools import tmscore` binds a *module*, not a callable | real API `tm_align(x, y, seqx, seqy)` (coords first), `tm_norm_chain2` |
