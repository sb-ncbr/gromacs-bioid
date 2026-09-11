---
name: validation-stats
description: >-
  Read-only monitoring of the live BAT3 validation campaign in
  ceitec-biodata-ns. Produces campaign statistics (S1-S7) via the on-NFS
  campaign_stats.py inside deploy/validation-api plus quick SQL pulses on
  deploy/validation-postgres. Covers queue pace, failure taxonomy, exact and
  similarity-based hit@K against MDDBR ground truth.
---

# Validation Stats Skill

## Purpose

Report trustworthy statistics for the running BAT3 validation campaign without touching pipeline state. Use it for progress pulses, full S1-S7 overviews, and similarity-based quality scoring (S7).

## Assets

- **Stats script**: `/data/validation/campaign_stats.py` (NFS; repo copy `scripts/campaign_stats.py` — redeploy to NFS after repo edits, via `kubectl exec -i deploy/validation-api -- sh -c "cat > /data/validation/campaign_stats.py" < scripts/campaign_stats.py`)
- **Run it in**: `deploy/validation-api` (only pod with `/data/validation` mount + sim caches at `/data/validation/sim_cache/`, `/data/validation/mddbr_meta_cache/`)
- **Postgres**: `deploy/validation-postgres`, `psql -U validation -d bat3_validation` (identity from secret `validation-postgres-secret`; no password needed in-pod)
- **Current artifacts**: `/data/validation/stats_full_sim.log`, `/data/validation/stats_full_sim.json`

## Modes

| Mode | Command shape | Cost |
|---|---|---|
| pulse | SQL counts on validation_queue + bat3_runs (see /validation-stats command) | seconds |
| full | `kubectl exec deploy/validation-api -n ceitec-biodata-ns -- python3 /data/validation/campaign_stats.py --full` | 1-8 min |
| sim | detached: `sh -c 'cd /data/validation && nohup python3 campaign_stats.py --full --sim --json-out /data/validation/stats_full_sim.json > /data/validation/stats_full_sim.log 2>&1 & echo "launched pid $!"'` | ~10 min background |
| log | `tail -40` / `grep -A8 "S7 SIMILARITY"` on stats_full_sim.log | seconds |
| entry N | `... --entry N` | seconds |

Long runs MUST use the detached nohup pattern (survives VPN drops); poll via `log` mode. Never run `--sim` in a foreground kubectl exec.

## Reading The Output

- **S1 pace**: last-1h completions is the honest rate (~1 run/min when download-bound); the script's ETA uses the 24h window and is distorted after incidents — ignore it.
- **S2 taxonomy**: known terminal classes are loading (data rejects), download, other. A NEW class is an incident — cross-check `.opencode/context/bat3/errors/common-issues.md` signatures.
- **S3**: healthy = ~94%+ of entries reaching export_results.
- **S4**: molecules/entry ~1.18 and verified-rate ~0.73 post-F1; smiles/inchi_key attempt counts must climb as v2.15-era results dominate.
- **S5 exact hit@K**: pessimistic lower bound (identifier drift). Never report it as quality.
- **S7 similarity hit@K**: AUTHORITATIVE. validated = sim>=0.9 in sequence space (pdb/uniprot) or fingerprint Tanimoto (inchikey). Healthy baselines (2026-09-11): pdb validated@1 >=95%, uniprot >=91%, entry-any >=94%. inchikey att% is a COVERAGE metric recovering with the requeue waves, not a quality regression.
- **630-class unmapped pairs** in S7 = uncached PubChem fingerprint fetches; usually transient, cache heals on rescore.

## Red Flags (report immediately, do not fix)

- failed_last_hour > ~10% of done_last_hour
- S7 pdb validated@1 < 90% on post-incident results
- OOMKilled restarts on validation-worker pods
- Celery depth nonzero for hours while queue has queued items (intake stall)

## Safety

- READ-ONLY: never requeue, kubectl patch/apply/delete, SQL UPDATE/INSERT, or file edits under this skill. Mutations belong to the incident workflow with explicit user approval.
- Do not `kubectl exec` interactive shells; use the exact command shapes above.

## Reference

- `/validation-stats` command (`.opencode/commands/validation-stats.md`) - invocation wrapper with SQL + recipes
- `.opencode/context/bat3/lookup/commands.md` - stats usage cheatsheet
- `.opencode/context/bat3/guides/full-scale-dispatch.md` - campaign runbook
- `.opencode/context/bat3/errors/common-issues.md` - incident signatures P0-1..P2-17
