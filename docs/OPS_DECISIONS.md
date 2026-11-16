# Operational decisions

Changes to the live CEITEC deployment that are not in the chart or the code.
Each entry records what changed, why, who decided it and how to undo it.

## 2026-11-16 — Per-address submission limit raised to 1000 runs/hour

- **Change:** `BAT3_SUBMIT_LIMIT_PER_HOUR=1000` on `bat3-ceitec-bat3-api` via
  `kubectl set env`. The code default is 30, and nothing else had set it.
- **Why:** the MD validation thesis (mdval, `ceitec-biodata-ns`) runs BioID on
  about 15,000 simulations from MD-Repo, ATLAS, Zenodo, Figshare, OSF and the
  part of MDDB the campaign did not cover. They are submitted through the
  public `POST /runs` API from one in-cluster client. At 30/hour that is about
  three weeks.
- **What still limits load:** `BAT3_QUEUE_CAP` (40 runs waiting) is
  unchanged. Submitters receive 429 and wait, so the worker fleet sets the
  pace and external services (RCSB PDB etc.) see no more load than the fleet
  produces. `bat3-ui-worker` runs at 15–25 replicas for the campaign.
- **Cleanup:** the mdval submitter deletes each run with its owner token after
  downloading `results.json`, and submits with `retention=1` as a fallback.
  This avoids the retention sweep's 50-runs-per-pass circuit breaker.
- **Side effect:** the higher limit applies to every address, including public
  users. The public docs (`docs/site/docs/rest-api.md`, `mcp.md`) still say 30
  per hour.
- **Decided by:** Tomáš Pavlík (owner). This env change, and this note, are the
  only changes to bat3 the mdval project is allowed to make.
- **Undo:** `kubectl -n ceitec-biodata-ns set env deploy/bat3-ceitec-bat3-api
  BAT3_SUBMIT_LIMIT_PER_HOUR-` (restores the code default, 30).
