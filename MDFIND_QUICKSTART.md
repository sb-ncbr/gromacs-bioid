# mdfind Backup - Quick Start 🚀

## One-Line Summary
**Built 71 MB index with 205K files for automatic S3 fallback when MDDBR is down.**

---

## 📦 What You Got

```
✅ Index file:        validation/data/mdfind_backup_index_full.json (71 MB)
✅ Lookup service:    validation/mdfind_index.py
✅ Download module:   validation/src/downloader_with_mdfind.py
✅ Tests:             validation/test_mdfind_fallback.py (4/4 passing)
✅ Docs:            docs/MDFIND_DEPLOYMENT_GUIDE.md
```

---

## 🚀 Deploy in 3 Steps

### 1. Copy Index
```bash
scp validation/data/mdfind_backup_index_full.json worker:/data/
```

### 2. Update Code
```python
# In your validation code
from validation.mdfind_index import MDFindIndex
from validation.src.downloader_with_mdfind import download_files

# Initialize
mdfind = MDFindIndex('/data/mdfind_backup_index_full.json')

# Download (automatic fallback)
files = download_files(
    files=mddb_files,
    dest_dir='/tmp/files',
    dataset_id='A0001',  # For mdfind lookup
    use_mdfind_fallback=True
)
```

### 3. Test
```bash
python -m validation.test_mdfind_fallback
# Expected: 4/4 tests passed ✅
```

---

## 📊 Stats

| Metric | Value |
|--------|-------|
| Datasets | 13,257 |
| Files | 205,399 |
| Coverage | ~60% |
| Index size | 71 MB |
| Lookup time | <1ms |
| Test pass | 4/4 ✅ |

---

## 🔍 Storage Providers

| Provider | Files | % |
|----------|-------|---|
| MDDBR | 139,561 | 68% |
| OSF | 32,528 | 16% |
| Zenodo | 31,314 | 15% |
| Figshare | 1,996 | 1% |

---

## 📚 Full Docs

- **Deploy**: `docs/MDFIND_DEPLOYMENT_GUIDE.md`
- **Architecture**: `docs/research/MDFIND_BACKUP_ARCHITECTURE.md`
- **Summary**: `docs/MDFIND_COMPLETE_SUMMARY.md`

---

**Status**: ✅ Production Ready | **Tests**: 4/4 Passing | **Deploy Time**: <10 min
