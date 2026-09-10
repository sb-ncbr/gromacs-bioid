# MDDB + S3 Architecture Analysis

**Date**: 2026-08-10  
**Status**: ✅ Complete Analysis

---

## 🎯 Executive Summary

This document describes the complete architecture for linking bat3 flat/wide table entries to MDDB IDs and implementing S3 fallback for file downloads.

---

## 📊 Database Architecture

### **Two Database Systems**

#### **1. MDDB PostgreSQL Database** (Remote - Production)
- **Location**: `db.mdfind.dyn.cloud.e-infra.cz:5432/mydb`
- **Access**: Via `db_readonly.py` read-only script ONLY
- **Size**: 337,427 files across 13,257 datasets
- **Purpose**: Master metadata repository

**Tables:**
```
datasets              - Dataset metadata (title, author, origin, etc.)
files                 - File metadata (file_url, file_type, size, md5)
metadata_definitions  - Available metadata attributes (211 types)
metadata_values       - Actual metadata values per file
embedding_values      - Static embedding data
static_embedding_values   - Static embeddings
dynamic_embedding_values - Dynamic embeddings
jobs                  - Processing jobs
```

#### **2. BAT3 SQLite Database** (Local - Indexed Cache)
- **Location**: `/home/tomsko/work/bat3/validation/data/mddb_index.db`
- **Size**: 3.8 GB
- **Purpose**: Local cache of MDDB entries for fast access

**Tables:**
```
mddb_entries          - Cached MDDB project metadata (7,643 entries)
mddb_files            - Cached file URLs (139,104 files)
bat3_runs             - Validation runs (2,494 runs)
ground_truth_signatures - Ground truth data (14,536 signatures)
bat3_hits             - Search results
bat3_segments         - Protein segments
bat3_signatures       - Generated signatures
validation_runs       - Validation job tracking
chem_cache            - Chemical structure cache
pdb_cache             - PDB structure cache
uniprot_cache         - UniProt cache
```

---

## 🔗 Linking Strategy

### **Primary Key Relationships**

```
BAT3 SQLite                          MDDB PostgreSQL
─────────────────────────────────────────────────────────────
mddb_entries                        datasets
  ├─ project_local_accession (PK) ───┤ dataset_id (PK)
  ├─ md_id                          │
  ├─ global_accession               │
  └─ metadata_json                  └─ title, author, description, etc.

mddb_files                          files
  ├─ entry_id (FK → mddb_entries)   │
  ├─ filename                       │
  ├─ file_type                      ├─ file_type
  ├─ url                            ├─ file_url
  └─ md5                            └─ file_md5

bat3_runs
  ├─ entry_id (FK → mddb_entries)
  ├─ local_accession
  ├─ global_accession
  └─ status, error_message, etc.

ground_truth_signatures
  ├─ entry_id (FK → mddb_entries)
  ├─ signature_type (sequence|structure|representation)
  ├─ signature_subtype
  ├─ signature_data
  └─ signature_value
```

### **Linking Flow**

```
bat3_runs
  ↓ (entry_id)
mddb_entries
  ├─ project_local_accession → datasets.dataset_id (MDDB)
  └─ md_id → MD internal identifier
  ↓ (id)
mddb_files
  └─ url → File download location
```

---

## 🗄️ Storage Locations (S3 Analysis)

### **File URL Distribution**

| Storage Provider | URL Pattern | File Count | Datasets |
|-----------------|-------------|------------|----------|
| **MDDBR** (Primary) | `https://mmb.mddbr.eu/api/rest/v1/` | 136,966 | 4,090 |
| **MDDBR (JSC)** | `https://jsc.mddbr.eu/api/rest/v1/` | 2,138 | - |
| **Zenodo** | `https://zenodo.org/records/` | 31,314 | 1,482 |
| **OSF** | `https://osf.io/download/` | 32,528 | 81 |
| **Figshare/ND** | `https://ndownloader.` | 1,996 | 595 |
| **TOTAL** | | **204,942** | **6,248+** |

### **S3 Storage Reality**

**Important Finding**: "S3" in this context actually means **multiple storage providers**, not just AWS S3:

1. **MDDBR Storage** (`mmb.mddbr.eu`)
   - Likely S3-backed object storage
   - 139,561 files (68% of total)
   - Primary authoritative source
   - URL pattern: `https://mmb.mddbr.eu/api/rest/v1/projects/{local_accession}/files/{filename}`

2. **External Repositories**
   - Zenodo (31,314 files)
   - OSF (32,528 files)
   - Figshare (1,996 files)
   - These are NOT on MDDBR S3

---

## 🔄 File Download Flow

### **Current Implementation**

```python
def download_simulation_files(entry_id: int):
    # 1. Get entry from local cache
    entry = db.query(MddbEntry).get(entry_id)
    
    # 2. Get files from local cache
    files = db.query(MddbFile).filter_by(entry_id=entry_id).all()
    
    # 3. Download from MDDBR API
    for file in files:
        url = f"https://mmb.mddbr.eu/api/rest/v1/projects/{entry.project_local_accession}/files/{file.filename}"
        response = requests.get(url, timeout=30)  # ❌ 100% failure when MDDBR down
        
    # 4. Validate against ground truth
    signatures = db.query(GroundTruthSignature).filter_by(entry_id=entry_id).all()
```

### **Problem**

- **MDDBR timeout**: 30s × 3 retries = 180s per failed entry
- **No fallback**: When MDDBR is down, ALL downloads fail
- **Success rate when MDDBR down**: 0%

---

## ✅ Proposed S3 Fallback Architecture

### **Option 1: S3 as Secondary Source** (RECOMMENDED)

```
download_simulation_files():
    1. Try MDDBR via db_readonly.py script
       ↓ (timeout/failure after 30s)
    2. Check if GroundTruthSignature exists for entry
       ↓ (exists = files likely available)
    3. Construct S3 URL from pattern
       ↓
       S3 URL = f"https://mmb.mddbr.eu/{local_accession}/{filename}"
       (Direct object storage, bypasses API)
    4. Download from S3
       ↓ (success)
    5. Validate checksums
    6. Continue validation
```

**Why This Works:**
- ✅ MDDBR remains authoritative source
- ✅ Minimal code changes
- ✅ Ground truth existence = reliable S3 indicator
- ✅ Can be disabled via config
- ❌ Adds ~30s latency when MDDBR fails (acceptable)

### **URL Pattern Discovery**

**MDDBR API URLs** (current):
```
https://mmb.mddbr.eu/api/rest/v1/projects/A0001/files/trajectory.xtc
https://mmb.mddbr.eu/api/rest/v1/projects/A0001/files/structure.pdb
```

**Potential S3 Direct URLs** (to be verified):
```
https://mmb.mddbr.eu/A0001/trajectory.xtc
https://mmb.mddbr.eu/A0001/structure.pdb
```

**External Repository URLs** (already direct):
```
https://zenodo.org/records/12345/files/simulation.xtc
https://osf.io/download/abc123/
```

---

## 🛠️ Implementation Requirements

### **Phase 1: Discovery (2-3 days)**

1. **Test S3 URL patterns**
   ```bash
   # Using db_readonly.py to get known entries
   python db_readonly.py -q "SELECT project_local_accession, filename, file_url FROM files LIMIT 10"
   
   # Test direct S3 access
   curl -I "https://mmb.mddbr.eu/A0001/trajectory.xtc"
   ```

2. **Verify ground truth assumption**
   ```sql
   -- Check if GroundTruthSignature existence correlates with S3 availability
   SELECT e.project_local_accession, 
          COUNT(DISTINCT f.file_id) as file_count,
          COUNT(DISTINCT gts.id) as signature_count
   FROM mddb_entries e
   LEFT JOIN mddb_files f ON e.id = f.entry_id
   LEFT JOIN ground_truth_signatures gts ON e.id = gts.entry_id
   GROUP BY e.project_local_accession
   HAVING signature_count > 0
   LIMIT 20;
   ```

3. **Understand db_readonly.py integration**
   - How to call from bat3 worker
   - Query interface (CLI args, JSON output)
   - Timeout/retry behavior
   - Error handling

### **Phase 2: S3 Client Implementation (2-3 days)**

```python
# s3_client.py
class S3Client:
    def __init__(self):
        self.base_url = "https://mmb.mddbr.eu"
        self.timeout = 60
        self.session = requests.Session()
    
    def download_file(self, local_accession: str, filename: str, dest_path: str) -> bool:
        """Download file directly from S3 storage"""
        url = f"{self.base_url}/{local_accession}/{filename}"
        
        try:
            response = self.session.get(url, timeout=self.timeout, stream=True)
            response.raise_for_status()
            
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return True
        except Exception as e:
            logger.error(f"S3 download failed: {e}")
            return False
    
    def check_file_exists(self, local_accession: str, filename: str) -> bool:
        """HEAD request to check file availability"""
        url = f"{self.base_url}/{local_accession}/{filename}"
        
        try:
            response = self.session.head(url, timeout=10)
            return response.status_code == 200
        except:
            return False
```

### **Phase 3: Fallback Logic (2-3 days)**

```python
# download_service.py
def download_simulation_files(entry_id: int, config: Config) -> DownloadResult:
    """Download files with MDDBR → S3 fallback"""
    
    # Get entry and files from local cache
    entry = db.query(MddbEntry).get(entry_id)
    files = db.query(MddbFile).filter_by(entry_id=entry_id).all()
    
    # Check for ground truth signatures
    has_ground_truth = (db.query(GroundTruthSignature)
                        .filter_by(entry_id=entry_id)
                        .first() is not None)
    
    download_results = []
    
    for file in files:
        result = FileDownloadResult(filename=file.filename)
        
        # Try 1: MDDBR via db_readonly.py (primary)
        success = try_mddbr_download(entry, file, config)
        
        # Try 2: S3 fallback
        if not success and has_ground_truth and config.s3_fallback_enabled:
            logger.info(f"MDDBR failed, trying S3 fallback for {file.filename}")
            success = try_s3_download(entry, file, config)
        
        # Try 3: External repository (if applicable)
        if not success and file.file_url:
            if is_external_url(file.file_url):
                logger.info(f"Trying external repository: {file.file_url}")
                success = try_external_download(file.file_url, config)
        
        result.success = success
        download_results.append(result)
    
    return DownloadResult(files=download_results)
```

### **Phase 4: Configuration**

```python
# config.py
class Config:
    # MDDBR settings
    MDFIND_DB_CONNECTION_STRING: str  # From .db_connection file
    MDFIND_SCRIPT_PATH: str = "/path/to/db_readonly.py"
    MDFIND_TIMEOUT: int = 30
    MDFIND_MAX_RETRIES: int = 3
    
    # S3 fallback settings
    S3_BASE_URL: str = "https://mmb.mddbr.eu"
    S3_FALLBACK_ENABLED: bool = True
    S3_TIMEOUT: int = 60
    S3_CHECK_EXISTS: bool = True  # HEAD request before download
    
    # Ground truth settings
    REQUIRE_GROUND_TRUTH: bool = True  # Only use S3 if ground truth exists
```

---

## 📊 Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| MDDBR success rate | >95% | ~70% (estimated) |
| S3 fallback success rate | >90% | N/A |
| Overall success rate (MDDBR down) | >85% | 0% |
| S3 fallback usage rate | <5% | N/A |
| Avg download time | <40s | 30s (MDDBR up) |
| Validation errors | No increase | Baseline |

---

## ⚠️ Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Silent data divergence** (S3 ≠ MDDBR API) | 🔴 High | Add checksum verification, compare MD5 |
| **S3 auth failures** | 🟡 Medium | Use IAM roles, test on startup |
| **Ground truth ≠ S3 files** | 🟡 Medium | HEAD request before download attempt |
| **Increased latency** | 🟡 Medium | Keep MDDBR timeout short (30s), S3 timeout 60s |
| **S3 costs** | 🟢 Low | Internal CEITEC storage, likely no cost |
| **db_readonly.py unavailable in K8s** | 🟡 Medium | Test in container, have fallback to direct API |

---

## 🔍 Key Questions for Team

1. **S3 URL pattern**: What is the exact pattern for direct S3 access?
   - `https://mmb.mddbr.eu/{local_accession}/{filename}`?
   - Or different bucket structure?

2. **Ground truth guarantee**: Does `GroundTruthSignature` existence guarantee files are on S3?

3. **db_readonly.py in K8s**: Can the script run from worker pods?
   - Network access to MDDB PostgreSQL?
   - Python dependencies installed?

4. **Authentication**: How to authenticate S3 requests from K8s pods?
   - IAM roles?
   - Access keys in secrets?
   - No auth needed (public bucket)?

5. **Who manages S3 upload**: Who maintains the S3 upload pipeline?
   - Need to verify sync between MDDBR API and S3

---

## 📅 Implementation Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| **Phase 1: Discovery** | 2-3 days | Test S3 URLs, verify ground truth, understand db_readonly.py |
| **Phase 2: S3 Client** | 2-3 days | Implement S3 client, test downloads |
| **Phase 3: Fallback Logic** | 2-3 days | Modify download service, add fallback |
| **Phase 4: Testing** | 2-3 days | Test scenarios, performance, verify assumptions |
| **Phase 5: Monitoring** | 1-2 days | Add metrics, alerts, dashboards |
| **TOTAL** | **9-14 days** | ~2 weeks |

---

## 🎯 Next Steps

1. **✅ Complete** - Analyzed database schemas
2. **✅ Complete** - Understood linking strategy
3. **✅ Complete** - Identified storage locations
4. **TODO** - Test S3 URL patterns with curl
5. **TODO** - Verify ground truth assumption with SQL queries
6. **TODO** - Test db_readonly.py integration
7. **TODO** - Implement PoC with 1-2 test entries

---

## 📚 Related Files

- **db_readonly.py**: `/home/tomsko/work/bat3/validation/example_mdfind/db_readonly.py`
- **mddb_index.db**: `/home/tomsko/work/bat3/validation/data/mddb_index.db`
- **S3 paths analysis**: `/home/tomsko/work/bat3/validation/example_mdfind/s3_storage_paths.json`
- **Previous research**: `/home/tomsko/work/bat3/docs/research/S3_FALLBACK_RESEARCH.md`

---

**Analysis Complete**: Ready for Phase 1 implementation upon team confirmation of S3 URL patterns and ground truth assumptions.
