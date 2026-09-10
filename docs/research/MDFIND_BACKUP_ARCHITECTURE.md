# mdfind Backup Architecture

**Date**: 2026-08-10  
**Status**: ✅ Requirements Clarified

---

## 🎯 Executive Summary

**mdfind** is a **read-only backup** of SOME MD files from MDDBR. It provides:
- PostgreSQL database with dataset/file metadata
- Public S3 URLs for direct file downloads
- **NOT authoritative** - MDDB is primary source
- **NOT complete** - only SOME files are backed up
- **NO ground truth guarantee** - S3 URLs may differ

**Implementation approach:**
1. Dump mdfind database to local index file (one-time/scheduled)
2. Validation workers use index for fallback when MDDB unavailable
3. Download directly from public S3 URLs in index
4. All operations **outside** mdfind namespace (no modifications)

---

## 🏗️ Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                        VALIDATION WORKFLOW                          │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐                                               │
│  │ 1. Try MDDB     │ ← Primary, Authoritative                     │
│  │    (Direct)     │ ← Always try first                           │
│  └────────┬────────┘                                               │
│           │                                                         │
│           │ Success                                                 │
│           ↓                                                         │
│  ┌─────────────────┐                                               │
│  │ Download &      │                                               │
│  │ Validate        │                                               │
│  └─────────────────┘                                               │
│                                                                     │
│           │ MDDB Unavailable                                        │
│           ↓                                                         │
│  ┌─────────────────┐                                               │
│  │ 2. Check        │ ← Local index file                           │
│  │    mdfind index │ ← Pre-built snapshot                         │
│  └────────┬────────┘                                               │
│           │                                                         │
│           │ Found in index                                          │
│           ↓                                                         │
│  ┌─────────────────┐                                               │
│  │ 3. Download     │ ← Public S3 URLs                             │
│  │    from S3      │ ← No authentication needed                   │
│  └────────┬────────┘                                               │
│           │                                                         │
│           │ Success                                                 │
│           ↓                                                         │
│  ┌─────────────────┐                                               │
│  │ Validate        │ ← May not have ground truth                  │
│  └─────────────────┘                                               │
│                                                                     │
│           │ Not in mdfind                                           │
│           ↓                                                         │
│  ┌─────────────────┐                                               │
│  │ Entry Fails     │ ← No backup available                        │
│  └─────────────────┘                                               │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

---

## 📊 System Components

### **1. MDDB (Primary)**

| Property | Value |
|----------|-------|
| **Role** | Authoritative source |
| **Access** | Direct API/database |
| **Completeness** | 100% (by definition) |
| **Ground Truth** | Yes |
| **Fallback** | No (primary) |

---

### **2. mdfind PostgreSQL (Backup Metadata)**

| Property | Value |
|----------|-------|
| **Role** | Read-only backup index |
| **Location** | `db.mdfind.dyn.cloud.e-infra.cz:5432/mydb` |
| **Access** | `db_readonly.py` script ONLY |
| **Completeness** | ~40-50% of MDDB (incomplete) |
| **Ground Truth** | NO guarantee |
| **Modification** | NEVER modify |

**Tables:**
```sql
datasets              -- Dataset metadata
files                 -- File metadata with S3 URLs
metadata_definitions  -- Available metadata types
metadata_values       -- Metadata values
embedding_values      -- Embedding data
```

**Key constraint:** This database is READ-ONLY. We can only:
- Query for data extraction
- Dump to local files
- NEVER modify schema or data

---

### **3. Local Index File (Pre-built)**

| Property | Value |
|----------|-------|
| **Role** | Fast lookup for validation workers |
| **Location** | `/data/mdfind_backup_index.json` |
| **Format** | JSON |
| **Refresh** | Scheduled (monthly?) |
| **Access** | Read-only by workers |

**Structure:**
```json
{
  "built_at": "2026-08-10T15:00:00Z",
  "total_datasets": 4090,
  "total_files": 139561,
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
          "s3_url": "https://mmb.mddbr.eu/...",
          "md5": "abc123...",
          "size_bytes": 123456789
        }
      ]
    }
  ]
}
```

---

### **4. S3 Storage (Public)**

| Property | Value |
|----------|-------|
| **Role** | File storage for mdfind backup |
| **Access** | Public HTTP(S) downloads |
| **Authentication** | None required |
| **URL Pattern** | Varies (from index) |
| **Guarantees** | None (may differ from MDDB) |

**URL Distribution:**

| Provider | Pattern | Files | % |
|----------|---------|-------|---|
| MDDBR | `https://mmb.mddbr.eu/...` | 136,966 | 67% |
| Zenodo | `https://zenodo.org/records/...` | 31,314 | 15% |
| OSF | `https://osf.io/download/...` | 32,528 | 16% |
| Figshare | `https://ndownloader....` | 1,996 | 1% |

**Important:** S3 URLs are stored in the `files.file_url` column. No pattern guarantee - use exact URL from index.

---

## 🔗 Data Flow

### **Index Building (Scheduled)**

```
┌──────────────────┐
│ mdfind PostgreSQL│
│ (remote)         │
└────────┬─────────┘
         │
         │ db_readonly.py
         │ SELECT d.dataset_id, f.file_url, ...
         │ FROM datasets d JOIN files f ...
         │
         ↓
┌──────────────────┐
│ Local JSON Index │
│ /data/mdfind_backup_index.json │
└────────┬─────────┘
         │
         │ Symlink update
         │
         ↓
┌──────────────────┐
│ Validation       │
│ Workers          │
└──────────────────┘
```

### **Validation Download (Runtime)**

```
┌──────────────────┐
│ Validation Entry │
│ (local_accession)│
└────────┬─────────┘
         │
         ↓
┌──────────────────┐     No      ┌──────────────────┐
│ Try MDDB first   │────────────→│ Entry Fails      │
│ (primary)        │             │                  │
└────────┬─────────┘             └──────────────────┘
         │
         │ MDDB unavailable
         ↓
┌──────────────────┐     No      ┌──────────────────┐
│ Check mdfind     │────────────→│ Entry Fails      │
│ index            │             │ (not in backup)  │
└────────┬─────────┘             └──────────────────┘
         │
         │ Found
         ↓
┌──────────────────┐
│ Download from    │
│ S3 (public URL)  │
└────────┬─────────┘
         │
         ↓
┌──────────────────┐
│ Validate         │
│ (no ground truth │
│  guarantee)      │
└──────────────────┘
```

---

## 🛠️ Implementation

### **Phase 1: Build Index** (1-2 days)

**Script:** `scripts/build_mdfind_index.py`

```python
#!/usr/bin/env python3
"""
Dump mdfind PostgreSQL database to local JSON index.
Run scheduled (e.g., monthly) to keep index fresh.
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

DB_READONLY_SCRIPT = Path(__file__).parent.parent / 'validation' / 'example_mdfind' / 'db_readonly.py'
OUTPUT_DIR = Path('/data/mdfind_indexes')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

QUERY = """
SELECT 
    d.dataset_id,
    d.dataset_origin,
    d.title,
    d.author,
    d.description,
    f.file_id,
    f.file_name as filename,
    f.file_type,
    f.file_url as s3_url,
    f.file_md5,
    f.file_size
FROM datasets d
JOIN files f ON d.dataset_id = f.dataset_id
WHERE f.file_url IS NOT NULL
ORDER BY d.dataset_id, f.file_name
"""

def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = OUTPUT_DIR / f'mdfind_backup_index_{timestamp}.json'
    
    print(f"Building mdfind index...")
    print(f"Output: {output_file}")
    
    # Execute query via db_readonly.py
    result = subprocess.run(
        [sys.executable, DB_READONLY_SCRIPT, '-q', QUERY, '--no-confirm'],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"ERROR: db_readonly.py failed: {result.stderr}")
        sys.exit(1)
    
    # Parse output (JSON format)
    # Note: db_readonly.py outputs human-readable table format
    # May need to modify to output JSON, or parse the table format
    
    # For now, assume we can get JSON output
    files_data = json.loads(result.stdout)
    
    # Group by dataset
    datasets = {}
    for row in files_data:
        dataset_id = row['dataset_id']
        if dataset_id not in datasets:
            datasets[dataset_id] = {
                'dataset_id': dataset_id,
                'dataset_origin': row['dataset_origin'],
                'title': row['title'],
                'author': row['author'],
                'description': row['description'],
                'files': []
            }
        
        datasets[dataset_id]['files'].append({
            'file_id': row['file_id'],
            'filename': row['filename'],
            'file_type': row['file_type'],
            's3_url': row['s3_url'],
            'md5': row['md5'],
            'size_bytes': row['file_size']
        })
    
    # Build final index
    index = {
        'built_at': datetime.now().isoformat(),
        'total_datasets': len(datasets),
        'total_files': sum(len(d['files']) for d in datasets.values()),
        'datasets': list(datasets.values())
    }
    
    # Write index
    with open(output_file, 'w') as f:
        json.dump(index, f, indent=2)
    
    print(f"✓ Built index: {len(datasets)} datasets, {index['total_files']} files")
    
    # Update latest symlink
    latest_link = OUTPUT_DIR / 'mdfind_backup_index_latest.json'
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(output_file)
    
    print(f"✓ Updated symlink: {latest_link} → {output_file}")

if __name__ == '__main__':
    main()
```

**Cron job (monthly):**
```bash
# /etc/cron.d/mdfind_index_refresh
0 2 1 * * root /usr/bin/python3 /path/to/scripts/build_mdfind_index.py >> /var/log/mdfind_index.log 2>&1
```

---

### **Phase 2: Index Lookup Service** (1-2 days)

**Module:** `validation/mdfind_index.py`

```python
"""
mdfind backup index lookup service.
Used by validation workers to find files when MDDB is unavailable.
"""

import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class FileRecord:
    file_id: str
    filename: str
    file_type: str
    s3_url: str
    md5: Optional[str]
    size_bytes: Optional[int]
    dataset_id: str

@dataclass
class DatasetRecord:
    dataset_id: str
    dataset_origin: str
    title: Optional[str]
    author: Optional[str]
    description: Optional[str]
    files: List[FileRecord]

class MDFindIndex:
    """
    Read-only lookup service for mdfind backup index.
    Thread-safe, loaded once at initialization.
    """
    
    def __init__(self, index_path: str):
        self.index_path = Path(index_path)
        
        if not self.index_path.exists():
            raise FileNotFoundError(f"mdfind index not found: {index_path}")
        
        logger.info(f"Loading mdfind index from {index_path}")
        
        with open(self.index_path) as f:
            self.data = json.load(f)
        
        # Build lookup tables
        self._datasets: Dict[str, DatasetRecord] = {}
        self._file_index: Dict[str, FileRecord] = {}
        
        for ds_data in self.data.get('datasets', []):
            files = [
                FileRecord(
                    file_id=f['file_id'],
                    filename=f['filename'],
                    file_type=f['file_type'],
                    s3_url=f['s3_url'],
                    md5=f.get('md5'),
                    size_bytes=f.get('size_bytes'),
                    dataset_id=ds_data['dataset_id']
                )
                for f in ds_data.get('files', [])
            ]
            
            dataset = DatasetRecord(
                dataset_id=ds_data['dataset_id'],
                dataset_origin=ds_data.get('dataset_origin', 'unknown'),
                title=ds_data.get('title'),
                author=ds_data.get('author'),
                description=ds_data.get('description'),
                files=files
            )
            
            self._datasets[dataset.dataset_id] = dataset
            
            for file in files:
                self._file_index[file.file_id] = file
        
        logger.info(
            f"Loaded mdfind index: {len(self._datasets)} datasets, "
            f"{len(self._file_index)} files"
        )
    
    def get_dataset(self, dataset_id: str) -> Optional[DatasetRecord]:
        """Get dataset by dataset_id"""
        return self._datasets.get(dataset_id)
    
    def has_dataset(self, dataset_id: str) -> bool:
        """Check if dataset exists in mdfind backup"""
        return dataset_id in self._datasets
    
    def get_files(self, dataset_id: str) -> List[FileRecord]:
        """Get all files for a dataset"""
        dataset = self._datasets.get(dataset_id)
        return dataset.files if dataset else []
    
    def get_file(self, file_id: str) -> Optional[FileRecord]:
        """Get file by file_id"""
        return self._file_index.get(file_id)
    
    def get_s3_url(self, dataset_id: str, filename: str) -> Optional[str]:
        """Get S3 URL for a specific file"""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return None
        
        for file in dataset.files:
            if file.filename == filename:
                return file.s3_url
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        return {
            'built_at': self.data.get('built_at'),
            'total_datasets': self.data.get('total_datasets'),
            'total_files': self.data.get('total_files'),
            'loaded_datasets': len(self._datasets),
            'loaded_files': len(self._file_index)
        }
```

---

### **Phase 3: Download Service Integration** (2-3 days)

**Module:** `validation/download_service.py`

```python
"""
Download service with MDDB → mdfind S3 fallback.
"""

import logging
import requests
import hashlib
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from .mdfind_index import MDFindIndex

logger = logging.getLogger(__name__)

@dataclass
class FileDownloadResult:
    filename: str
    success: bool
    source: str  # 'mddb' or 'mdfind_backup'
    error: Optional[str] = None
    downloaded_path: Optional[str] = None

@dataclass
class DownloadResult:
    files: List[FileDownloadResult]
    source: str
    total_files: int
    successful: int
    failed: int

class MddbUnavailableError(Exception):
    """Raised when MDDB is unavailable"""
    pass

class DownloadFailedError(Exception):
    """Raised when download fails"""
    pass

class DownloadService:
    def __init__(self, config):
        self.config = config
        self.mdfind_index = MDFindIndex(config.mdfind_index_path)
        self.session = requests.Session()
    
    def download_simulation_files(self, entry) -> DownloadResult:
        """
        Download files with MDDB → mdfind S3 fallback.
        
        Args:
            entry: MddbEntry object with local_accession, project_local_accession, etc.
        
        Returns:
            DownloadResult with file download status
        """
        # Try 1: Primary MDDB access
        try:
            logger.info(f"Attempting MDDB download for {entry.local_accession}")
            return self._download_from_mddb(entry)
        except MddbUnavailableError as e:
            logger.warning(f"MDDB unavailable for {entry.local_accession}: {e}")
        
        # Try 2: mdfind backup S3
        if self.config.mdfind_fallback_enabled:
            logger.info(f"Attempting mdfind backup for {entry.local_accession}")
            try:
                return self._download_from_mdfind_backup(entry)
            except DownloadFailedError as e:
                logger.error(f"mdfind backup failed for {entry.local_accession}: {e}")
        
        # All options exhausted
        raise DownloadFailedError(
            f"Entry {entry.local_accession} not available from MDDB or mdfind backup"
        )
    
    def _download_from_mddb(self, entry) -> DownloadResult:
        """
        Download from primary MDDB.
        (Existing implementation - not shown)
        """
        # ... existing MDDB download logic ...
        pass
    
    def _download_from_mdfind_backup(self, entry) -> DownloadResult:
        """
        Download from mdfind S3 backup.
        """
        dataset_id = entry.project_local_accession
        
        # Check if in mdfind index
        if not self.mdfind_index.has_dataset(dataset_id):
            raise DownloadFailedError(
                f"Dataset {dataset_id} not in mdfind backup"
            )
        
        # Get files from index
        files = self.mdfind_index.get_files(dataset_id)
        if not files:
            raise DownloadFailedError(
                f"No files found for {dataset_id} in mdfind backup"
            )
        
        logger.info(
            f"Found {len(files)} files for {dataset_id} in mdfind backup"
        )
        
        # Download each file from S3
        results = []
        for file in files:
            result = self._download_file_from_s3(file, entry)
            results.append(result)
        
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        return DownloadResult(
            files=results,
            source='mdfind_backup',
            total_files=len(results),
            successful=successful,
            failed=failed
        )
    
    def _download_file_from_s3(self, file, entry) -> FileDownloadResult:
        """
        Download single file from public S3 URL.
        """
        s3_url = file.s3_url
        filename = file.filename
        expected_md5 = file.md5
        
        # Build destination path
        dest_dir = Path(self.config.download_dir) / entry.local_accession
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename
        
        try:
            logger.debug(f"Downloading {filename} from {s3_url[:50]}...")
            
            response = self.session.get(
                s3_url,
                timeout=self.config.mdfind_s3_timeout,
                stream=True
            )
            response.raise_for_status()
            
            # Download in chunks
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Verify MD5 if provided
            if expected_md5:
                actual_md5 = self._calculate_md5(dest_path)
                if actual_md5 != expected_md5:
                    logger.warning(
                        f"MD5 mismatch for {filename}: "
                        f"expected {expected_md5}, got {actual_md5}"
                    )
                    # Don't fail - mdfind doesn't guarantee ground truth
            
            logger.info(f"Successfully downloaded {filename} from mdfind backup")
            
            return FileDownloadResult(
                filename=filename,
                success=True,
                source='mdfind_backup',
                downloaded_path=str(dest_path)
            )
        
        except requests.RequestException as e:
            logger.error(f"S3 download failed for {filename}: {e}")
            return FileDownloadResult(
                filename=filename,
                success=False,
                source='mdfind_backup',
                error=str(e)
            )
        
        except Exception as e:
            logger.error(f"Unexpected error downloading {filename}: {e}")
            return FileDownloadResult(
                filename=filename,
                success=False,
                source='mdfind_backup',
                error=str(e)
            )
    
    def _calculate_md5(self, filepath: Path) -> str:
        """Calculate MD5 hash of file"""
        hash_md5 = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
```

---

### **Phase 4: Configuration** (1 day)

**File:** `config.py`

```python
from pydantic import BaseSettings, Field
from pathlib import Path

class Config(BaseSettings):
    # =====================
    # MDDB (Primary)
    # =====================
    mddb_url: str = Field(
        default="https://mddb.example.com",
        description="Primary MDDB API URL"
    )
    mddb_timeout: int = Field(
        default=30,
        description="MDDB request timeout (seconds)"
    )
    mddb_max_retries: int = Field(
        default=3,
        description="Max retries for MDDB requests"
    )
    
    # =====================
    # mdfind Backup
    # =====================
    mdfind_index_path: Path = Field(
        default=Path("/data/mdfind_backup_index_latest.json"),
        description="Path to mdfind backup index JSON file"
    )
    mdfind_fallback_enabled: bool = Field(
        default=True,
        description="Enable mdfind S3 fallback"
    )
    mdfind_s3_timeout: int = Field(
        default=60,
        description="S3 download timeout (seconds)"
    )
    
    # =====================
    # Download Settings
    # =====================
    download_dir: Path = Field(
        default=Path("/data/downloads"),
        description="Base directory for downloaded files"
    )
    
    # =====================
    # Index Refresh
    # =====================
    mdfind_index_refresh_days: int = Field(
        default=30,
        description="Rebuild mdfind index every N days"
    )
    
    class Config:
        env_prefix = "BAT3_"
        env_file = ".env"
```

**Environment variables:**
```bash
# .env
BAT3_MDDB_URL=https://mddb.example.com
BAT3_MDDB_TIMEOUT=30
BAT3_MDFIND_INDEX_PATH=/data/mdfind_backup_index_latest.json
BAT3_MDFIND_FALLBACK_ENABLED=true
BAT3_MDFIND_S3_TIMEOUT=60
BAT3_DOWNLOAD_DIR=/data/downloads
```

---

## 📊 Success Metrics

| Metric | Target | Notes |
|--------|--------|-------|
| Index build time | <10 min | One-time/scheduled |
| Index size | <500 MB | JSON file |
| Lookup latency | <1 ms | In-memory index |
| S3 download success rate | >80% | For entries in mdfind |
| Overall recovery rate | 30-40% | When MDDB down |
| Validation errors | No increase | Despite fallback |

---

## ⚠️ Constraints & Limitations

### **What mdfind IS:**
- ✅ Read-only backup of SOME MD files
- ✅ Public S3 URLs for direct download
- ✅ Useful fallback when MDDB unavailable
- ✅ No authentication required

### **What mdfind IS NOT:**
- ❌ Authoritative source (MDDB is)
- ❌ Complete backup (only ~40-50% of files)
- ❌ Ground truth guarantee
- ❌ Direct URL mapping (URLs may differ)
- ❌ Modifiable (read-only only)

### **Implementation Constraints:**
1. **NO modifications** to mdfind project or database
2. **db_readonly.py** = read-only access only
3. **Local index** = separate from mdfind namespace
4. **S3 downloads** = outside mdfind infrastructure
5. **No guarantees** on file availability or correctness

---

## 📅 Implementation Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| **Phase 1: Build Index** | 1-2 days | Create dump script, test output, set up cron |
| **Phase 2: Lookup Service** | 1-2 days | Implement MDFindIndex class, unit tests |
| **Phase 3: Download Integration** | 2-3 days | Modify download service, add fallback logic |
| **Phase 4: Configuration** | 1 day | Add config options, environment variables |
| **Phase 5: Testing** | 2-3 days | Test with real entries, measure success rates |
| **TOTAL** | **7-11 days** | ~1.5 weeks |

---

## 🎯 Next Steps

1. **Confirm S3 URL format** - Check actual URLs in mdfind database
2. **Test index build script** - Run db_readonly.py query, verify output
3. **Implement lookup service** - Create MDFindIndex class
4. **Modify download service** - Add mdfind fallback logic
5. **Test end-to-end** - Validate with entries known to be in mdfind

---

## 📚 Related Files

- **db_readonly.py**: `/home/tomsko/work/bat3/validation/example_mdfind/db_readonly.py`
- **mddb_index.db**: `/home/tomsko/work/bat3/validation/data/mddb_index.db`
- **Index output**: `/data/mdfind_backup_index.json` (to be created)
- **Previous research**: `/home/tomsko/work/bat3/docs/research/S3_FALLBACK_RESEARCH.md`

---

**Architecture Approved**: Ready for implementation pending confirmation of constraints.
