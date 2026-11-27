# Validation campaign rerun (g2)

A g1‑style rerun of the MDposit validation campaign through the BioID
**repository queue**, with the server's default configuration (decision
2026‑11‑26). Each entry's downloaded input is read in place, and its results
end up next to the earlier arms as `/data/validation/<entry>/results-g2.json`.
The scoring scripts run unchanged on that file name.

| Piece | What it does |
|---|---|
| `POST /api/v1/runs` `campaign_input=<entry>/input` | Repository queue + `X-Queue-Token` only. Links the files of `$BAT3_CAMPAIGN_INPUT_ROOT/<entry>/input` (default `/data/validation`) into the run's input directory. The path is confined to that root, symlinks are resolved, there are no uploads and no 128 MiB limit. |
| `scripts/campaign_rerun.py` | One run per entry that has `results-g1.json` (15,133 entries). Deterministic run ids `g2-<entry>`, ≤ 32 in flight. Follows each run to a terminal status (the repository queue's own auto‑retries included) and copies `results.json` → `results-g2.json`. Resumable via `/data/validation/rerun-g2/state.json`. |
| `k8s/campaign-rerun-g2-job.yaml` | The runner as a Job (released image, campaign data + runs volumes). |
| `scripts/campaign_stats.py` | The paper's scorer (S7, `S7_VERIFIED_ONLY`, `S7_SHARD`, `S7_DUMP`), now in the repo. Same arithmetic as `bioid_bughunt/scripts/g1_exports`. |
| `scripts/s7_score.sh`, `scripts/s7_merge.py` | Sharded S7 pass over the repo‑worker pods, then the merge. |

## Steps

1. **Release** the branch (BioID API + workers; `docs/` and the release procedure).
   mdval must have drained first: the rerun shares the repository queue.
2. **E2E checks** on the deployed build: the canary entries (water + duplicate ions,
   modified RNA, AMBER prmtop H rename, DOG membrane, NMA‑capped ACE2, mmCIF‑heavy
   ligands). Compare them with g1.
3. **Token secret**: use the *existing* repository token. Issuing a new one on the
   admin page replaces mdval's.
   ```
   kubectl -n ceitec-biodata-ns create secret generic bioid-campaign-queue-token \
     --from-literal=token=<repository queue token>
   ```
4. **Dry run**: set the Job args to `--dry-run`. The log must show 15133 entries.
5. **Smoke**: run with `--limit 20`. Check that 20 `results-g2.json` files appeared and
   look sane against `results-g1.json` (stages, top hits).
6. **Full run**: remove the limit and re‑apply the Job (it resumes). Expect several days
   at 32 slots. Progress is logged every 5 min (`kubectl logs job/bioid-campaign-rerun-g2`).
7. **Scoring**:
   ```
   cp /data/validation/sim_cache/pairs.jsonl /data/validation/sim_cache/pairs.jsonl.bak-pre-g2
   ARM=g2 VERIFIED=1 REVALIDATE_ZEROS=1 DATABASE_URL=postgresql://... scripts/s7_score.sh launch
   ARM=g2 VERIFIED=1 scripts/s7_score.sh status
   ARM=g2 VERIFIED=1 scripts/s7_score.sh merge journal/draft/data/s7_full_g2_verified.json
   ```
   For the default‑mode table, run the same with `VERIFIED=0`. The first pass with
   `REVALIDATE_ZEROS=1` heals the cached zeros that g2 reads (GitHub #36).

## Comparability with g1

g2 uses today's server defaults, not g1's evaluation config. It therefore adds UniRef50,
SwissLipids, ChEBI, SIFTS and AlphaFind, and drops `formula_chembl`, `name_manual` and
`guess_missing_bonds`. A difference against g1 is the product as it is now, not the
code changes alone.
