# mdfind Backup Index - Implementation Complete

**Date**: 2026-08-10  
**Status**: ✅ **COMPLETE & READY TO DEPLOY**

---

## 🎯 Summary

Built a complete local index of the mdfind PostgreSQL database for use as MDDB fallback during validation. The index contains **205,399 files** across **13,257 datasets** from multiple storage providers (MDDBR, Zenodo, OSF, Figshare).

---

## 📊 Index Statistics

| Metric | Value |
|--------|-------|
| **Total datasets** | 13,257 |
| **Datasets with files** | 6,248 |
| **Total files** | 205,399 |
| **Index file size** | 71.4 MB |
| **Build time** | ~5 minutes |

### **Storage Provider Breakdown**

| Provider | Files | % |
|----------|-------|---|
| **MDDBR** (mmb.mddbr.eu) | 139,561 | 67.9% |
| **OSF** | 32,528 | 15.8% |
| **Zenodo** | 31,314 | 15.2% |
| **Figshare** | 1,996 | 1.0% |

---

## 📁 Files Created

### **1. Index File** (Deploy to workers)
```
Location: /home/tomsko/work/bat3/validation/data/mdfind_backup_index_full.json
Size: 71.4 MB
Format: JSON
```

**Structure:**
```json
{
  "built_at": "2026-08-10T15:41:44.574095",
  "source": "mdfind PostgreSQL database (complete dump)",
  "stats": {
    "total_datasets": 13257,
    "datasets_with_files": 6248,
    "total_files": 205399
  },
  "datasets": [
    {
      "dataset_id": "A0001",
      "dataset_origin": "mddbr",
      "title": "MoDEL 12CA",
      "files": [
        {
          "file_id": "uuid-123",
          "filename": "trajectory.xtc",
          "file_type": "xtc",
          "s3_url": "https://mmb.mddbr.eu/api/rest/v1/projects/A0001/files/trajectory.xtc",
          "md5": "abc123...",
          "size_bytes": 123456789
        }
      ]
    }
  ]
}
```

### **2. Build Script** (One-time use)
```
Location: /home/tomsko/work/bat3/scripts/build_mdfind_index_full.py
Purpose: Build index from mdfind PostgreSQL database
Usage: python scripts/build_mdfind_index_full.py
```

### **3. Lookup Service** (Used by validation workers)
```
Location: /home/tomsko/work/bat3/validation/mdfind_index.py
Purpose: Fast in-memory lookup of datasets/files
Usage: from validation.mdfind_index import MDFindIndex
```

---

## 🔧 Usage

### **In Validation Code**

```python
from validation.mdfind_index import MDFindIndex

# Initialize (once per worker process)
index = MDFindIndex('/path/to/mdfind_backup_index_full.json')

# Check if dataset exists in mdfind
if index.has_dataset('A0001'):
    # Get all files for dataset
    files = index.get_files('A0001')
    
    # Download each file from S3
    for file in files:
        s3_url = file['s3_url']
        filename = file['filename']
        expected_md5 = file['md5']
        
        # Download from public S3 URL
        response = requests.get(s3_url, timeout=60)
        response.raise_for_status()
        
        with open(dest_path / filename, 'wb') as f:
            f.write(response.content)
        
        # Verify MD5 if available
        if expected_md5:
            actual_md5 = calculate_md5(dest_path / filename)
            assert actual_md5 == expected_md5
```

### **API Reference**

```python
index = MDFindIndex(index_path)

# Check existence
index.has_dataset('A0001')  # bool

# Get metadata
index.get_dataset('A0001')  # dict or None
index.get_stats()  # dict with statistics

# Get files
index.get_files('A0001')  # list of file dicts
index.get_file(file_id)  # dict or None
index.get_s3_url('A0001', 'trajectory.xtc')  # str or None

# Get all URLs for dataset
index.get_all_s3_urls('A0001')  # list of URL strings

# Search by origin
index.search_by_origin('mddbr')  # list of dataset_ids

# Identify provider
index.get_url_pattern(url)  # 'mddbr', 'zenodo', 'osf', 'figshare', 'unknown'
```

---

## 🏗️ Integration with Validation Flow

### **Current Flow (MDDB only)**
```
1. Get entry from local cache
2. Download from MDDB API
3. Validate against ground truth
```

### **New Flow (MDDB → mdfind fallback)**
```
1. Get entry from local cache
2. Try MDDB API
   ↓ (unavailable)
3. Check mdfind index
   ↓ (found)
4. Download from S3 (public URLs)
5. Validate against ground truth (already available)
```

### **Implementation Location**

Modify `validation/download_service.py`:

```python
from validation.mdfind_index import MDFindIndex

class DownloadService:
    def __init__(self, config):
        self.config = config
        self.mdfind_index = MDFindIndex(config.mdfind_index_path)
    
    def download_simulation_files(self, entry) -> DownloadResult:
        # Try 1: Primary MDDB
        try:
            return self._download_from_mddb(entry)
        except MddbUnavailableError:
            pass
        
        # Try 2: mdfind backup
        if self.config.mdfind_fallback_enabled:
            return self._download_from_mdfind(entry)
        
        raise DownloadFailedError("Entry not available")
    
    def _download_from_mdfind(self, entry) -> DownloadResult:
        dataset_id = entry.project_local_accession
        
        if not self.mdfind_index.has_dataset(dataset_id):
            raise DownloadFailedError(f"Not in mdfind: {dataset_id}")
        
        files = self.mdfind_index.get_files(dataset_id)
        results = []
        
        for file in files:
            success = self._download_from_s3(file['s3_url'], file)
            results.append(success)
        
        return DownloadResult(files=results, source='mdfind_backup')
```

---

## ⚙️ Configuration

```python
# config.py
class Config:
    # mdfind backup settings
    mdfind_index_path: Path = Path("/data/mdfind_backup_index_full.json")
    mdfind_fallback_enabled: bool = True
    mdfind_s3_timeout: int = 60
    
    # MDDB settings (primary)
    mddb_timeout: int = 30
    mddb_max_retries: int = 3
```

**Environment variables:**
```bash
BAT3_MDFIND_INDEX_PATH=/data/mdfind_backup_index_full.json
BAT3_MDFIND_FALLBACK_ENABLED=true
BAT3_MDFIND_S3_TIMEOUT=60
```

---

## 📈 Expected Performance

| Metric | Target | Notes |
|--------|--------|-------|
| Index load time | <1s | 71 MB JSON, in-memory |
| Lookup latency | <1ms | Dict-based lookup |
| S3 download success | >80% | For entries in mdfind |
| Recovery rate (MDDB down) | 30-40% | Depends on entry coverage |
| Memory usage | ~200 MB | Loaded index + structures |

---

## ⚠️ Important Notes

### **What mdfind IS:**
- ✅ Complete dump of mdfind PostgreSQL database
- ✅ Public S3 URLs for direct download
- ✅ One-time build (no refresh needed)
- ✅ Fast in-memory lookup
- ✅ Multiple storage providers

### **What mdfind IS NOT:**
- ❌ Authoritative source (MDDB is)
- ❌ Complete coverage (only 6,248/13,257 datasets have files)
- ❌ Modifiable (read-only index)
- ❌ Ground truth source (ground truth already exists separately)

### **URLs are EXACT:**
- Use S3 URLs exactly as stored in index
- No pattern matching or construction needed
- Different providers have different URL formats

---

## 🚀 Deployment Steps

### **1. Copy Index to Workers**
```bash
# Copy to validation worker nodes
scp /home/tomsko/work/bat3/validation/data/mdfind_backup_index_full.json \
    worker-node:/data/mdfind_backup_index_full.json
```

### **2. Deploy Lookup Service**
```bash
# Copy mdfind_index.py to validation package
cp /home/tomsko/work/bat3/validation/mdfind_index.py \
   /path/to/validation/package/validation/
```

### **3. Update Configuration**
```bash
# Add to worker environment
echo "BAT3_MDFIND_INDEX_PATH=/data/mdfind_backup_index_full.json" >> /etc/environment
echo "BAT3_MDFIND_FALLBACK_ENABLED=true" >> /etc/environment
```

### **4. Test Integration**
```python
# Test on worker node
from validation.mdfind_index import MDFindIndex

index = MDFindIndex('/data/mdfind_backup_index_full.json')
print(f"Loaded {index.get_stats()['total_files']:,} files")

# Test lookup
if index.has_dataset('A0001'):
    files = index.get_files('A0001')
    print(f"Found {len(files)} files for A0001")
```

---

## 📝 URL Patterns

### **MDDBR** (67.9% of files)
```
https://mmb.mddbr.eu/api/rest/v1/projects/{dataset_id}/files/{filename}
https://jsc.mddbr.eu/api/rest/v1/projects/{dataset_id}/files/{filename}
```

### **Zenodo** (15.2%)
```
https://zenodo.org/api/records/{record_id}/files/{filename}/content
```

### **OSF** (15.8%)
```
https://osf.io/download/{file_id}/
```

### **Figshare** (1.0%)
```
https://ndownloader.figshare.com/files/{file_id}
```

---

## 🧪 Testing

### **Test Index Integrity**
```bash
python validation/mdfind_index.py /data/mdfind_backup_index_full.json
```

### **Test Sample Downloads**
```python
import requests
from validation.mdfind_index import MDFindIndex

index = MDFindIndex('/data/mdfind_backup_index_full.json')

# Test MDDBR URL
files = index.get_files('A0001')
if files:
    url = files[0]['s3_url']
    response = requests.head(url, timeout=10)
    print(f"{url}: {response.status_code}")
```

---

## 📚 Related Files

| File | Location | Purpose |
|------|----------|---------|
| **Index file** | `validation/data/mdfind_backup_index_full.json` | Main index (71 MB) |
| **Lookup service** | `validation/mdfind_index.py` | Python API |
| **Build script** | `scripts/build_mdfind_index_full.py` | One-time build |
| **Architecture doc** | `docs/research/MDFIND_BACKUP_ARCHITECTURE.md` | Design specs |

---

## ✅ Completion Checklist

- [x] Dump mdfind PostgreSQL database
- [x] Handle 10K row limit (pagination)
- [x] Export all 13,257 datasets
- [x] Export all 205,399 files with URLs
- [x] Build JSON index (71 MB)
- [x] Create lookup service
- [x] Test lookup functionality
- [x] Document usage
- [ ] Deploy to worker nodes
- [ ] Integrate with download service
- [ ] Test end-to-end fallback

---

**Status**: Ready for deployment. Index built and tested locally. Next step: deploy to worker nodes and integrate with validation download service.

