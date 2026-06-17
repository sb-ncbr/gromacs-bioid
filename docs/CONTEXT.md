# bat3 Project Context

**Generated:** June 12, 2026  
**Purpose:** Portable project state summary for continuing work on a different machine

---

## Section 1: Project Goal

**bat3** is a molecular identification pipeline for structural biology simulations. It processes molecular dynamics (MD) trajectories and identifies molecules using various strategies including sequence-based identification.

### Current Focus: Fixing BLAST/Sequence Search

The immediate goal is to make protein/nucleotide sequence identification work end-to-end. When a user provides a trajectory with protein/nucleotide segments, the pipeline should:

1. Extract sequences from the trajectory
2. Run BLAST against appropriate databases (nr, Swiss-Prot, PDB)
3. Return meaningful identifiers (UniProt IDs, PDB IDs, etc.)
4. Link identified molecules to external knowledge bases

**Success criterion:** A real FASTA sequence from a GROMACS trajectory returns BLAST hits with valid identifiers.

---

## Section 2: Root Causes Found and Fixed

### Bug 1: Segid Quoting (Empty Fragments → No Signatures)

| Aspect | Details |
|--------|---------|
| **Problem** | GROMACS segment names with spaces (e.g., `"Protein in water t= 80000.00000"`) caused MDAnalysis `select_atoms(f"segid {name}")` to return empty AtomGroups |
| **Impact** | All signatures failed with `"Segment '' not found"` |
| **Fix** | Replaced string-based selection with boolean indexing: `atoms[atoms.segids == segment_name]` |
| **Files Changed** | `src_new/loader/universe_facade.py`, `src/loader/simulation.py` |
| **Tests** | `tests/src_new/loader/test_universe_facade.py` - regression test added |

### Bug 2: BLAST Silent Failure (No Identifiers Ever Returned)

| Aspect | Details |
|--------|---------|
| **Problem** | `IdentifierResolutionError` was caught and swallowed with `return []` in `_run_blast_identity`/`_run_blast_similarity`, making failures invisible |
| **Impact** | Every run showed "attempted" BLAST resolvers but 0 hits. Users never saw a single sequence identifier. |
| **Fix** | Removed the error-swallowing try/except; errors now propagate to base class and get logged properly |
| **Files Changed** | `src_new/identification/resolvers/blast.py` |
| **Tests** | `tests/src_new/identification/test_resolvers.py` + `test_blast_integration.py` (47 tests total) |

---

## Section 3: Infrastructure Built

### PVC Sizing

The default 50Gi PVC was insufficient for BLAST databases (nr alone needs ~100GB compressed, ~200GB uncompressed).

```yaml
# bat3-chart/values.yaml
databasesData:
  size: 2Ti  # Changed from 50Gi
```

Template: `bat3-chart/templates/pvc-databases-data.yaml`

### Database Download Scripts

| Script | Purpose |
|--------|---------|
| `scripts/populate_blast_databases.py` | Downloads NCBI BLAST databases. Supports two strategies: (1) `update_blastdb.pl` if available, (2) direct HTTP via Python stdlib `urllib.request` + `tarfile` as fallback. Features atomic staging + symlink swap, MD5 verification, blastdbcmd verification, old snapshot cleanup |
| `scripts/k8s/run-download.sh` | Creates a standalone **Pod** (not Job) for downloading. Better than Job because logs persist until pod is deleted, no backoff limit, easy to exec into for debugging |
| `scripts/k8s/scale-worker.sh` | Scales worker deployment up/down (needed because worker uses most quota) |
| `scripts/k8s/check-status.sh` | Dashboard showing deployments, pods, PVCs, quotas |
| `scripts/k8s/get-job-logs.sh` | Stream logs from download pod |
| `scripts/k8s/exec-into-pod.sh` | Quick exec into pod for debugging |
| `scripts/k8s/copy-script-to-pod.sh` | Copy latest script into running pod without rebuild |
| `k8s/blast-db-download-job.yaml` | Standalone K8s manifest (moved OUT of Helm templates because Job spec.template is immutable) |

### BLAST Resolver Updates

**Configuration (`src_new/config/loader.py` BlastConfig):**

```python
blast_aa_db_path = "/app/databases/nr/nr"
swissprot_aa_db_path = "/app/databases/swissprot/swissprot"
pdb_aa_db_path = "/app/databases/pdbaa/pdbaa"
pdb_nt_db_path = "/app/databases/pdbnt/pdbnt"
core_nt_db_path = "/app/databases/core_nt/core_nt"
nt_db_path = "/app/databases/nt/nt"
```

**config.ini `[blast]` section:**

```ini
[blast]
aa_db_path = /app/databases/nr/nr
swissprot_aa_db_path = /app/databases/swissprot/swissprot
pdb_aa_db_path = /app/databases/pdbaa/pdbaa
pdb_nt_db_path = /app/databases/pdbnt/pdbnt
core_nt_db_path = /app/databases/core_nt/core_nt
nt_db_path = /app/databases/nt/nt
```

**Resolvers implemented (`src_new/identification/resolvers/blast.py`):**

| Resolver | Database | Type |
|----------|----------|------|
| `BLASTResolverPDBAA` | pdbaa | Protein |
| `BLASTResolverPDBNT` | pdbnt | Nucleotide |
| `BLASTResolverUNIPROT` | swissprot | Protein (fallback for uniprot_aa_db) |
| `BLASTResolverNR` | nr | Protein (non-redundant) |
| `BLASTResolverSWISSPROT` | swissprot | Protein (curated) |

**Registry (`src_new/identification/registry.py`):** All 5 resolvers registered

**Toggles (`src_new/config/loader.py` IdentifiersConfig + `config.ini`):**

```ini
[identifiers.resolvers.blast]
enabled_pdbaa = true
enabled_pdbnt = true
enabled_uniprot = true
enabled_nr = true
enabled_swissprot = true
```

---

## Section 4: Current State of the Cluster

**Status: Mid-migration** - The user was in the middle of database infrastructure setup when the session ended.

### Checklist for New Machine

Run this first to assess cluster state:

```bash
./scripts/k8s/check-status.sh
```

Expected findings (verify each):

- [ ] **PVC State**: `bat3-bat3-databases-data` may be missing or still at 50Gi
  - User deleted the old PVC but may not have re-run `helm upgrade` yet
  
- [ ] **Worker Deployment**: Scaled to 0 replicas
  - `kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns get deployment bat3-worker`
  - The download script scales worker down to free quota
  
- [ ] **Download Pod/Job**: May exist in failed state or not exist
  - Old failed Job may need cleanup: `kubectl delete job bat3-blast-db-download -n gromacs-bioid-ns`
  
- [ ] **Databases**: Not yet downloaded
  - The populate script has not successfully run yet
  
- [ ] **Quota Usage**: Should show available resources after worker scaled down
  - Worker uses ~4 CPU / ~10 Gi RAM when running

---

## Section 5: Immediate Next Steps

**Do these first on the new machine:**

### Step 1: Verify Cluster State

```bash
./scripts/k8s/check-status.sh
```

Check output for:
- PVC exists and is 2Ti
- Worker deployment status
- Available quota

### Step 2: Fix PVC if Needed

If PVC is missing or still at 50Gi:

```bash
# Scale worker down first (required for PVC deletion)
./scripts/k8s/scale-worker.sh down

# Delete old PVC if it exists
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns delete pvc bat3-bat3-databases-data

# Re-create via helm with 2Ti
helm upgrade --install bat3 bat3-chart/ --namespace gromacs-bioid-ns

# Verify new PVC
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns get pvc bat3-bat3-databases-data
```

### Step 3: Download Databases

**Option A: Use the run-download pod approach (recommended - no rebuild)**

```bash
# Start temp pod with PVC mounted
./scripts/k8s/run-download.sh --databases swissprot,pdbaa,pdbnt --follow

# If pod starts but can't find script, copy it in
./scripts/k8s/copy-script-to-pod.sh bat3-blast-db-download

# Exec into pod to run manually
./scripts/k8s/exec-into-pod.sh bat3-blast-db-download

# Inside pod:
python /app/scripts/populate_blast_databases.py \
    --target-dir /app/databases \
    --databases swissprot,pdbaa,pdbnt
```

**Option B: Rebuild Docker image with latest code**

```bash
# At repo root
docker build -f Dockerfile.worker -t cerit.io/tomsko/bat3-worker:latest .
docker push cerit.io/tomsko/bat3-worker:latest

# Then restart worker to pick up new image
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns rollout restart deployment bat3-worker
```

### Step 4: Scale Worker Back Up

```bash
./scripts/k8s/scale-worker.sh up
```

### Step 5: Verify Databases Are Accessible

```bash
# Check inside worker pod
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns exec deployment/bat3-worker -- \
    blastdbcmd -db /app/databases/swissprot -info

kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns exec deployment/bat3-worker -- \
    blastdbcmd -db /app/databases/pdbaa -info

kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns exec deployment/bat3-worker -- \
    blastdbcmd -db /app/databases/pdbnt -info
```

### Step 6: End-to-End Test

Run the integration tests to verify BLAST works:

```bash
python -m pytest tests/src_new/identification/test_blast_integration.py -v --tb=short
```

---

## Section 6: Blockers / Known Issues

| Issue | Severity | Workaround |
|-------|----------|------------|
| `update_blastdb.pl` not in worker image | Medium | urllib fallback implemented but untested in production |
| urllib fallback untested in real pod | Medium | Test with small databases first (pdbaa, pdbnt) |
| PVC must be 2Ti before downloading nr/core_nt | High | These need ~1TB each; don't attempt until PVC confirmed at 2Ti |
| Image rebuild may be needed | Low | Use copy-script-to-pod.sh to avoid rebuild |
| Resource quota is tight | Medium | Worker uses 4 CPU / ~10 Gi; download pod competes for same quota |
| End-to-end BLAST verification pending | High | Need real trajectory test with known sequences |

---

## Section 7: Test Status

### Passing Tests

| Suite | Count | Status |
|-------|-------|--------|
| Identification tests | 78 | ✅ Pass (30 pre-existing + 48 new) |
| Signature tests | 22 | ✅ Pass |
| Molecule tests | 14 | ✅ Pass |
| Input tests | 22 | ✅ Pass |
| Pipeline I/O tests | ~10 | ✅ Pass (slow, ~180s) |

### Known Failures (Unrelated to BLAST)

- API tests: Some failures exist, not blocking BLAST work
- Verification tests: Some failures exist, not blocking BLAST work

### Test Commands

```bash
# All identification tests
python -m pytest tests/src_new/identification/ -v --tb=short

# BLAST-specific tests
python -m pytest tests/src_new/identification/test_blast_integration.py -v

# Resolver unit tests
python -m pytest tests/src_new/identification/test_resolvers.py -v

# Loader tests (segid fix verification)
python -m pytest tests/src_new/loader/test_universe_facade.py -v
```

---

## Section 8: Files You Need to Bring

**Critical infrastructure files (must exist on new machine):**

```
scripts/k8s/
├── check-status.sh
├── copy-script-to-pod.sh
├── exec-into-pod.sh
├── get-job-logs.sh
├── run-download.sh
└── scale-worker.sh

scripts/
├── populate_blast_databases.py
├── download-databases.sh
├── validate_databases.py
└── fix-pvc-size.sh

k8s/
└── blast-db-download-job.yaml
```

**Source code changes:**

```
src_new/
├── loader/universe_facade.py          # segid boolean indexing fix
├── identification/resolvers/blast.py  # BLAST resolver implementation
├── identification/registry.py         # resolver registration
└── config/loader.py                   # BlastConfig, IdentifiersConfig

config.ini                              # [blast] section, resolver toggles
bat3-chart/values.yaml                  # databasesData.size: 2Ti
```

**Tests:**

```
tests/src_new/
├── identification/test_blast_integration.py
├── identification/test_resolvers.py
└── loader/test_universe_facade.py
```

---

## Section 9: Reference Commands

### Quick Status Check

```bash
./scripts/k8s/check-status.sh
```

### Scale Worker

```bash
./scripts/k8s/scale-worker.sh down   # Free quota for download
./scripts/k8s/scale-worker.sh up     # Resume processing
```

### Database Download

```bash
# Start download pod
./scripts/k8s/run-download.sh --databases swissprot,pdbaa,pdbnt --follow

# Follow logs
./scripts/k8s/get-job-logs.sh --follow

# Copy updated script into running pod
./scripts/k8s/copy-script-to-pod.sh bat3-blast-db-download

# Exec into pod
./scripts/k8s/exec-into-pod.sh bat3-blast-db-download
```

### Database Verification

```bash
# Check database info
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns exec deployment/bat3-worker -- \
    blastdbcmd -db /app/databases/swissprot -info

# Validate all databases
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns exec deployment/bat3-worker -- \
    python /app/scripts/validate_databases.py --target-dir /app/databases
```

### Run Tests

```bash
# All identification tests
python -m pytest tests/src_new/identification/ -v --tb=short

# Specific test file
python -m pytest tests/src_new/identification/test_blast_integration.py -v

# With coverage
python -m pytest tests/src_new/identification/ --cov=src_new/identification --cov-report=term-missing
```

### Kubectl Quick Reference

```bash
# Namespace alias
export K8S_NS="gromacs-bioid-ns"
export KUBE="--kubeconfig ~/.kube/config -n $K8S_NS"

# Get all resources
kubectl $KUBE get all

# Describe PVC
kubectl $KUBE describe pvc bat3-bat3-databases-data

# Get pod logs
kubectl $KUBE logs -f pod/bat3-blast-db-download

# Delete failed job
kubectl $KUBE delete job bat3-blast-db-download

# Check quota
kubectl $KUBE describe resourcequota
```

---

## Appendix: Database Sizes Reference

| Database | Type | Compressed | Uncompressed | Download Time (100 Mbps) |
|----------|------|------------|--------------|--------------------------|
| swissprot | Protein | ~70 MB | ~200 MB | ~1 min |
| pdbaa | Protein | ~500 MB | ~1.5 GB | ~5 min |
| pdbnt | Nucleotide | ~100 MB | ~300 MB | ~2 min |
| nr | Protein | ~100 GB | ~200 GB | ~3 hours |
| core_nt | Nucleotide | ~50 GB | ~100 GB | ~1.5 hours |
| nt | Nucleotide | ~150 GB | ~300 GB | ~4 hours |

**Recommendation:** Start with `swissprot,pdbaa,pdbnt` for testing (~2 GB total). Download `nr` and `core_nt` only when 2Ti PVC is confirmed.

---

**End of Context Document**
