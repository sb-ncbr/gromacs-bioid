# mdfind Backup Deployment Guide

**Date**: 2026-08-10  
**Status**: ✅ **READY FOR PRODUCTION**

---

## 🎯 Overview

Deploy mdfind backup index to enable automatic S3 fallback when MDDBR is unavailable during validation.

**What was built:**
- Complete index of mdfind PostgreSQL database (205,399 files)
- Python lookup service for fast dataset/file queries
- Integration with existing download module
- Full test suite (all tests passing ✅)

---

## 📦 Deployment Artifacts

| File | Location | Size | Purpose |
|------|----------|------|---------|
| **mdfind_backup_index_full.json** | `validation/data/` | 71 MB | Main index file |
| **mdfind_index.py** | `validation/` | 9 KB | Lookup service |
| **downloader_with_mdfind.py** | `validation/src/` | 10 KB | Download with fallback |
| **test_mdfind_fallback.py** | `validation/` | 8 KB | Integration tests |

---

## 🚀 Deployment Steps

### **Step 1: Copy Index to Worker Nodes**

```bash
# On deployment machine
cd /home/tomsko/work/bat3

# Copy to all worker nodes
for worker in worker1 worker2 worker3; do
    scp validation/data/mdfind_backup_index_full.json \
        ${worker}:/data/mdfind_backup_index_full.json
done
```

**Alternative**: Mount shared storage:
```bash
# If workers share storage with build machine
ln -s /home/tomsko/work/bat3/validation/data/mdfind_backup_index_full.json \
      /data/mdfind_backup_index_full.json
```

---

### **Step 2: Deploy Python Modules**

```bash
# Copy lookup service to validation package
cp validation/mdfind_index.py /path/to/validation/package/validation/

# Copy enhanced downloader (or merge with existing)
cp validation/src/downloader_with_mdfind.py \
   /path/to/validation/package/validation/src/downloader.py

# Copy test script (optional, for verification)
cp validation/test_mdfind_fallback.py \
   /path/to/validation/package/validation/
```

---

### **Step 3: Update Configuration**

Add to worker environment (`/etc/environment` or `.env`):

```bash
# mdfind backup configuration
BAT3_MDFIND_INDEX_PATH=/data/mdfind_backup_index_full.json
BAT3_MDFIND_FALLBACK_ENABLED=true
BAT3_MDFIND_S3_TIMEOUT=60
```

Or in `config.ini`:
```ini
[mdfind]
index_path = /data/mdfind_backup_index_full.json
fallback_enabled = true
s3_timeout = 60
```

---

### **Step 4: Initialize mdfind Index in Code**

In your validation startup code (e.g., `cli.py` or `orchestrator.py`):

```python
from validation.mdfind_index import MDFindIndex

# Initialize at application startup
mdfind_index = MDFindIndex('/data/mdfind_backup_index_full.json')

# Make available to download service
config.mdfind_index = mdfind_index
```

---

### **Step 5: Update Download Service**

Modify `validation/src/downloader.py` to use the enhanced version with mdfind fallback:

```python
# Option 1: Replace entire file
# cp downloader_with_mdfind.py downloader.py

# Option 2: Merge key functions
from .downloader_with_mdfind import download_files, download_from_mdfind

# Update download_files calls to include dataset_id and fallback
downloaded_paths = download_files(
    files=files,
    dest_dir=dest_dir,
    use_mdfind_fallback=True,
    dataset_id=entry.local_accession,  # For mdfind lookup
)
```

---

### **Step 6: Verify Deployment**

Run integration tests on each worker:

```bash
# SSH to worker
ssh worker1

# Run tests
cd /path/to/validation
python -m validation.test_mdfind_fallback
```

**Expected output:**
```
✓ Index loaded successfully
  Total datasets: 13,257
  Total files: 205,399

✓ PASS: Index loading
✓ PASS: Dataset lookup
✓ PASS: S3 URL accessibility
✓ PASS: Actual download

Total: 4/4 tests passed
```

---

## 🔧 Integration Points

### **Where to Hook In**

The mdfind fallback integrates at the **file download layer**:

```
Validation Flow:
  1. Select entry for validation
  2. Get file list from local cache
  3. Download files ← INTEGRATE HERE
     ├─ Try MDDBR (primary)
     └─ Try mdfind S3 (fallback)
  4. Validate against ground truth
  5. Report results
```

### **Code Location**

Modify `validation/src/downloader.py`:

```python
# Existing function signature
def download_files(
    files: list["MddbFile"],
    dest_dir: str | Path,
    verify: bool = True,
    retry: int = 3,
    ...
) -> list[Path]:

# Add new parameters
def download_files(
    files: list["MddbFile"],
    dest_dir: str | Path,
    verify: bool = True,
    retry: int = 3,
    use_mdfind_fallback: bool = True,  # NEW
    dataset_id: Optional[str] = None,   # NEW
    ...
) -> list[Path]:
```

### **Call Site Updates**

Find where `download_files` is called and add dataset_id:

```python
# Example: in validation worker
from validation.src.downloader import download_files

# Before
downloaded = download_files(files, dest_dir)

# After
downloaded = download_files(
    files,
    dest_dir,
    use_mdfind_fallback=True,
    dataset_id=entry.local_accession  # Pass dataset ID for lookup
)
```

---

## 📊 Expected Performance

| Metric | Target | Notes |
|--------|--------|-------|
| Index load time | <1s | 71 MB JSON |
| Memory usage | ~200 MB | In-memory index |
| Lookup latency | <1ms | Dict-based |
| S3 download success | >80% | For entries in mdfind |
| Recovery rate (MDDB down) | 30-40% | Overall improvement |

---

## ⚙️ Configuration Options

### **Enable/Disable Fallback**

```python
# Enable (default)
use_mdfind_fallback=True

# Disable (for testing MDDB-only)
use_mdfind_fallback=False
```

### **Timeout Settings**

```python
# MDDBR timeout (primary)
timeout=30

# mdfind S3 timeout (fallback)
timeout=60  # Longer for large files
```

### **Retry Logic**

```python
# Both MDDBR and mdfind use exponential backoff
retry=3  # Attempts: 1, 2, 3
# Delays: 1s, 2s, 4s
```

---

## 🧪 Testing Checklist

- [ ] Index file copied to worker nodes
- [ ] Lookup service imports correctly
- [ ] Download service updated
- [ ] Integration tests pass
- [ ] Test with MDDBR available (should use primary)
- [ ] Test with MDDBR unavailable (should use fallback)
- [ ] Verify downloaded files match ground truth
- [ ] Monitor error logs for fallback usage

---

## 📈 Monitoring

### **Log Messages to Watch For**

```
# Successful fallback
INFO: MDDBR download failed for trajectory.xtc: Connection timeout
INFO: Attempting mdfind fallback for trajectory.xtc
INFO: Successfully downloaded trajectory.xtc from mdfind backup

# Failed fallback
WARNING: MDDBR download failed for structure.pdb
WARNING: mdfind fallback failed for structure.pdb: File not in index
ERROR: Failed to download structure.pdb from all sources
```

### **Metrics to Track**

1. **Fallback usage rate**: % of downloads using mdfind
2. **Fallback success rate**: % of mdfind downloads successful
3. **Recovery improvement**: Overall success rate increase
4. **Download latency**: MDDBR vs mdfind comparison

---

## ⚠️ Troubleshooting

### **Index Not Found**

```
ERROR: Failed to load mdfind index: FileNotFoundError
```

**Fix**: Verify index path and permissions:
```bash
ls -lh /data/mdfind_backup_index_full.json
chmod 644 /data/mdfind_backup_index_full.json
```

### **No Files in Index**

```
WARNING: File trajectory.xtc not found in mdfind index
```

**Explanation**: Not all MDDB files are in mdfind backup (only ~60% coverage)

**Action**: This is expected. Entry will fail validation if not in either source.

### **S3 Download Fails**

```
WARNING: mdfind download attempt 1 failed: Connection timeout
```

**Fix**: 
- Check network connectivity to storage provider
- Increase timeout: `BAT3_MDFIND_S3_TIMEOUT=120`
- Verify URL is accessible: `curl -I "s3_url"`

---

## 📚 Related Documentation

- **Architecture**: `docs/research/MDFIND_BACKUP_ARCHITECTURE.md`
- **Implementation**: `docs/research/MDFIND_INDEX_IMPLEMENTATION.md`
- **Build Script**: `scripts/build_mdfind_index_full.py`
- **API Reference**: `validation/mdfind_index.py` (docstrings)

---

## ✅ Deployment Sign-Off

- [ ] Index deployed to all worker nodes
- [ ] Python modules updated
- [ ] Configuration applied
- [ ] Tests passing on all workers
- [ ] Monitoring configured
- [ ] Rollback plan documented

**Rollback**: If issues arise, set `BAT3_MDFIND_FALLBACK_ENABLED=false` to disable fallback and revert to MDDBR-only behavior.

---

**Ready for production deployment.** All tests passing. Documentation complete.

