# Guide: Reprocessing Validation Entries + Scoring hit@K

## Core Concept
How the Sept-2026 campaign reprocessed cached entries offline (bypassing the scheduler) and computed validation metrics against ground truth.

## Dispatch reprocessing (from a validation-worker pod)

```python
import os, psycopg2
from celery import Celery
con=psycopg2.connect(os.environ['DATABASE_URL'])
ids=[r[0] for r in con.cursor().execute('SELECT DISTINCT entry_id FROM bat3_runs')]
app=Celery('validation', broker=os.environ['CELERY_BROKER_URL'],
           backend=os.environ['CELERY_RESULT_BACKEND'])
for eid in ids:
    inp=f'/data/validation/{eid}/input'
    if not os.path.isdir(inp) or not os.listdir(inp): continue
    app.send_task('src_new.api.tasks.run_pipeline_task', kwargs={
        'run_id': f'reprocN-{eid}-<ts>',
        'input_dir': inp,
        'results_path': f'/data/validation/{eid}/results-vN.json',
        'config_path': '/data/validation/config_shared.ini',
    })
```

## Prerequisites
- Worker image ≥ current production tag (check `lookup/ceitec-deployment.md`); BLAST DBs visible at `/app/databases`
- `config_shared.ini` on NFS = tuned config (nr/core_nt/nt OFF for speed; per-pod resolver cache = `identifiers_cache.directory:` EMPTY)
- Entry dirs at 0777 (chmod via validation-worker, the owner uid)
- Do NOT reuse the corrupt shared cache: `/app/runs/resolver_cache.sqlite3.corrupt-*` stays archived

## Score hit@K vs ground truth

```bash
# from a bat3-worker pod (uid 1000 — results files are uid-1000 0600)
kubectl exec <worker> -- python3 /data/validation/offline_hit_k.py --pattern results-vN.json          # preview
kubectl exec <worker> -- python3 /data/validation/offline_hit_k.py --pattern results-vN.json --write-db # persist to validation_results
```
- GT source: Postgres `ground_truth_signatures` (types `uniprot`, `pdb` — bare ids)
- Metric: fraction of GT ids within top-K verified_hits (ranked by final_confidence)
- Script repo home: `bat3_validation/scripts/offline_hit_k.py`

## Verify a new pipeline image BEFORE mass dispatch
1. `docker run --rm <img> python3 -c "<import checks>"`
2. Dispatch ONE entry; poll `AsyncResult`; expect `verified_hits > 0` in its results file
3. Then bulk dispatch

## Reference
- `../errors/common-issues.md` — known failure signatures to check results for
- `../lookup/ceitec-deployment.md` — pods/mounts/paths
