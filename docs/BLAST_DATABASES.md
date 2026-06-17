# BLAST Databases Guide

**Purpose:** Reference documentation for BLAST database management in bat3

**Last Updated:** 2026-06-13

---

## Database Overview

bat3 uses NCBI BLAST databases to identify protein and nucleotide sequences from molecular dynamics trajectories. This document covers database selection, sizing, download strategies, and verification.

---

## Database Sizes

| Database | Description | Type | Compressed | Uncompressed | Download Priority |
|----------|-------------|------|------------|--------------|-------------------|
| `swissprot` | UniProtKB/Swiss-Prot (curated) | Protein | ~70 MB | ~200 MB | **High** - Start here |
| `pdbaa` | PDB protein sequences | Protein | ~500 MB | ~1.5 GB | **High** - Structure IDs |
| `pdbnt` | PDB nucleotide sequences | Nucleotide | ~100 MB | ~300 MB | **High** - Structure IDs |
| `nr` | Non-redundant protein | Protein | ~100 GB | ~200 GB | Medium - Comprehensive |
| `core_nt` | Core nucleotide collection | Nucleotide | ~50 GB | ~100 GB | Medium |
| `nt` | Nucleotide collection | Nucleotide | ~150 GB | ~300 GB | Low - Largest |

### Storage Requirements

- **Minimum (testing):** 5 GB PVC for `swissprot`, `pdbaa`, `pdbnt`
- **Recommended:** 500 Gi PVC for small/medium databases
- **Full:** 2 Ti PVC required for `nr` and `core_nt`

---

## PVC Sizing Guidance

### Check Current PVC Size

```bash
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns get pvc bat3-bat3-databases-data -o jsonpath='{.spec.resources.requests.storage}'
```

### Change PVC Size

PVC size changes require deletion and recreation:

```bash
# 1. Scale worker down (required)
./scripts/k8s/scale-worker.sh down

# 2. Update values.yaml
# Edit bat3-chart/values.yaml:
# databasesData:
#   size: 2Ti

# 3. Delete old PVC
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns delete pvc bat3-bat3-databases-data

# 4. Re-run helm upgrade
helm upgrade --install bat3 bat3-chart/ --namespace gromacs-bioid-ns

# 5. Verify new size
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns get pvc bat3-bat3-databases-data
```

### Why 2Ti?

The 2Ti size accommodates:
- `nr` database: ~200 GB uncompressed + snapshots
- `core_nt` database: ~100 GB uncompressed + snapshots
- `swissprot`, `pdbaa`, `pdbnt`: ~2 GB total
- Headroom for database updates and temporary files

---

## Download Strategy

### Two Download Methods

The `scripts/populate_blast_databases.py` script supports two strategies:

#### Method 1: update_blastdb.pl (Preferred)

```bash
update_blastdb.pl --decompress swissprot
```

**Pros:**
- Official NCBI tool
- Handles checksums automatically
- Supports incremental updates

**Cons:**
- Not included in Debian `ncbi-blast+` package
- Requires Perl and additional dependencies

#### Method 2: urllib Fallback (Default in bat3)

```bash
python scripts/populate_blast_databases.py --target-dir /app/databases --databases swissprot,pdbaa,pdbnt
```

**How it works:**
1. Downloads `.tar.gz` from NCBI FTP
2. Verifies MD5 checksum
3. Extracts to staging directory
4. Verifies with `blastdbcmd -info`
5. Atomic symlink swap to final location
6. Cleans old snapshots

**Pros:**
- No additional dependencies (Python stdlib only)
- Works in minimal Docker images
- Same atomic safety guarantees

**Cons:**
- Full download every time (no incremental)
- Untested at scale (as of June 2026)

### Download Commands

```bash
# Download specific databases
./scripts/k8s/run-download.sh --databases swissprot,pdbaa,pdbnt --follow

# Download all (requires 2Ti PVC)
./scripts/k8s/run-download.sh --databases all --follow

# Monitor progress
./scripts/k8s/get-job-logs.sh --follow
```

---

## Update Cadence

### Recommended Schedule

| Database | Update Frequency | Reason |
|----------|------------------|--------|
| `swissprot` | Weekly | Curated, frequent updates |
| `pdbaa`/`pdbnt` | Weekly | PDB releases weekly |
| `nr` | Monthly | Large, slower changing |
| `core_nt` | Monthly | Moderate size |
| `nt` | Quarterly | Very large |

### Automated Updates

Set up a cron job or Kubernetes CronJob:

```yaml
# Example CronJob (add to k8s/ directory)
apiVersion: batch/v1
kind: CronJob
metadata:
  name: blast-db-update
  namespace: gromacs-bioid-ns
spec:
  schedule: "0 2 * * 0"  # Weekly on Sunday at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: updater
            image: cerit.io/tomsko/bat3-worker:latest
            command:
            - python
            - /app/scripts/populate_blast_databases.py
            - --target-dir
            - /app/databases
            - --databases
            - swissprot,pdbaa,pdbnt
            volumeMounts:
            - name: databases-data
              mountPath: /app/databases
          volumes:
          - name: databases-data
            persistentVolumeClaim:
              claimName: bat3-bat3-databases-data
          restartPolicy: OnFailure
```

---

## Verification Commands

### blastdbcmd Info

```bash
# Check database metadata
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns exec deployment/bat3-worker -- \
    blastdbcmd -db /app/databases/swissprot -info

# Expected output includes:
# - Database name
# - Number of sequences
# - Total letters
# - Date created
```

### validate_databases.py

```bash
# Full validation suite
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns exec deployment/bat3-worker -- \
    python /app/scripts/validate_databases.py --target-dir /app/databases

# Validates:
# - File existence
# - MD5 checksums
# - blastdbcmd readability
# - Minimum sequence count
```

### Quick Test Queries

```bash
# Search for a known protein (e.g., ubiquitin)
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns exec deployment/bat3-worker -- \
    blastp -query /tmp/ubiquitin.fasta -db /app/databases/swissprot -outfmt 6 -max_target_seqs 5

# Expected: Multiple hits with UniProt IDs
```

---

## Troubleshooting

### Common Issues

#### "Database not found"

```bash
# Check if database files exist
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns exec deployment/bat3-worker -- \
    ls -la /app/databases/

# Verify symlinks point to actual data
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns exec deployment/bat3-worker -- \
    ls -la /app/databases/swissprot*
```

#### "Insufficient disk space"

```bash
# Check PVC usage
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns exec deployment/bat3-worker -- \
    df -h /app/databases

# If near capacity, delete old snapshots
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns exec deployment/bat3-worker -- \
    find /app/databases -name "*.tar.gz*" -mtime +7 -delete
```

#### "Download timeout"

The urllib fallback may timeout on large databases. Solutions:

1. Increase timeout in `populate_blast_databases.py`
2. Use `update_blastdb.pl` if available
3. Download externally and copy to PVC

```bash
# Copy pre-downloaded database to PVC
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns cp \
    /path/to/local/swissprot.tar.gz \
    bat3-blast-db-download:/tmp/

# Then extract manually inside pod
```

#### "blastdbcmd fails on extracted database"

This indicates corrupted download or extraction:

```bash
# Delete and re-download
kubectl --kubeconfig ~/.kube/config -n gromacs-bioid-ns exec deployment/bat3-worker -- \
    rm -rf /app/databases/swissprot*

# Re-run download
python /app/scripts/populate_blast_databases.py \
    --target-dir /app/databases \
    --databases swissprot
```

---

## Configuration

### Database Paths in Configuration

#### config.ini `[blast]` section

```ini
[blast]
blastp_exec = /usr/bin/blastp
blastn_exec = /usr/bin/blastn
nr_aa_db = /app/databases/nr/nr
swissprot_aa_db = /app/databases/swissprot/swissprot
pdb_aa_db = /app/databases/pdbaa/pdbaa
pdb_nt_db = /app/databases/pdbnt/pdbnt
core_nt_db = /app/databases/core_nt/core_nt
nt_db = /app/databases/nt/nt
blastp_num_threads = 1
blastn_num_threads = 1
max_target_seqs = 500
timeout_s = 300
local_instance_run_short_search_if_under_X_residues = 30
```

#### src_new/config/loader.py BlastConfig

```python
@dataclass
class BlastConfig:
    blastp_exec: str = "/usr/bin/blastp"
    blastn_exec: str = "/usr/bin/blastn"
    nr_aa_db: str = "/app/databases/nr/nr"           # non-redundant protein
    swissprot_aa_db: str = "/app/databases/swissprot/swissprot"  # curated protein
    pdb_aa_db: str = "/app/databases/pdbaa/pdbaa"       # PDB protein sequences
    pdb_nt_db: str = "/app/databases/pdbnt/pdbnt"       # PDB nucleotide sequences
    core_nt_db: str = "/app/databases/core_nt/core_nt"    # core nucleotide
    nt_db: str = "/app/databases/nt/nt"              # full nucleotide
    blastp_num_threads: int = 1
    blastn_num_threads: int = 1
    max_target_seqs: int = 500
    timeout_s: int = 300
    local_instance_run_short_search_if_under_X_residues: int = 30
    exact_match_max_evalue: float = 1e-50
    exact_match_min_bits: int = 51
    exact_match_min_identity_p: float = 0.99
    exact_match_min_query_cov_p: float = 0.99
    similarity_match_max_evalue: float = 0.1
    similarity_match_min_bits: int = 20
    similarity_match_min_identity_p: float = 0.4
```

### BLAST Thresholds

BLAST hits are classified as **exact** (identity) or **similarity** matches based on thresholds:

#### Exact Match Thresholds (identity hits)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `exact_match_max_evalue` | `1e-50` | Maximum acceptable e-value (lower = more significant) |
| `exact_match_min_bits` | `51` | Minimum bit score |
| `exact_match_min_identity_p` | `0.99` | Minimum identity (99%) |
| `exact_match_min_query_cov_p` | `0.99` | Minimum query coverage (99%) |

#### Similarity Match Thresholds

| Parameter | Default | Description |
|-----------|---------|-------------|
| `similarity_match_max_evalue` | `0.1` | Maximum acceptable e-value |
| `similarity_match_min_bits` | `20` | Minimum bit score |
| `similarity_match_min_identity_p` | `0.4` | Minimum identity (40%) |

### Resolver Mapping

The following BLAST resolvers are available in the `[identifiers]` section:

| Resolver Config Key | Database | Type | Similarity Toggle |
|---------------------|----------|------|-------------------|
| `blast_pdb_protein` | pdbaa | Protein | `blast_pdb_protein_similarity` |
| `blast_pdb_nucleic` | pdbnt | Nucleotide | `blast_pdb_nucleic_similarity` |
| `blast_uniprot` | swissprot | Protein | `blast_uniprot_similarity` |
| `blast_nr_protein` | nr | Protein | `blast_nr_protein_similarity` |
| `blast_swissprot_protein` | swissprot | Protein | `blast_swissprot_protein_similarity` |
| `blast_core_nt` | core_nt | Nucleotide | `blast_core_nt_similarity` |
| `blast_nt` | nt | Nucleotide | `blast_nt_similarity` |

### Enable/Disable Resolvers

In `config.ini`:

```ini
[identifiers]
blast_pdb_protein = yes
blast_pdb_protein_similarity = yes
blast_uniprot = yes
blast_uniprot_similarity = yes
blast_nr_protein = yes
blast_nr_protein_similarity = yes
blast_swissprot_protein = yes
blast_swissprot_protein_similarity = yes
blast_pdb_nucleic = yes
blast_pdb_nucleic_similarity = yes
blast_core_nt = yes
blast_core_nt_similarity = yes
blast_nt = yes
blast_nt_similarity = yes
```

---

## Reading Results

### Understanding Identifier Hits

When viewing results in the UI or API:

- **Identity hits**: Displayed with score "Identity" in the UI. These are exact or near-exact matches meeting the strict exact-match thresholds.
- **Similarity hits**: Displayed with an identity percentage (e.g., "85%"). These are homologous matches meeting the more relaxed similarity thresholds.

### BLAST-Specific Metadata

BLAST hits include additional metadata columns:

| Field | Description |
|-------|-------------|
| `evalue` | BLAST e-value (expectation value) |
| `bit_score` | BLAST bit score |
| `identity_percent` | Sequence identity percentage (0-100) |
| `coverage_percent` | Query coverage percentage (0-100) |

### UI Display

The RunResults page shows a "Top Identifiers" card on the Overview tab when identifier data exists, displaying:
- Total hit count
- Number of resolvers attempted and failed
- Top 5 hits sorted by score (identity hits treated as 100%)
- External link buttons for hits with database URLs

---

## Reference: NCBI FTP URLs

Databases are downloaded from:

```
ftp://ftp.ncbi.nlm.nih.gov/blast/db/
```

File naming convention:

```
{database_name}.{number}.tar.gz
```

Example for swissprot (single file):
```
swissprot.tar.gz
```

Example for nr (multiple files):
```
nr.00.tar.gz
nr.01.tar.gz
...
nr.62.tar.gz
```

MD5 checksums are available at:
```
ftp://ftp.ncbi.nlm.nih.gov/blast/db/{database_name}.tar.gz.md5
```

---
