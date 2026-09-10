# MDDBR Download with S3 Fallback - Research & Planning

## Executive Summary

**Goal**: Implement MDDBR file download with automatic fallback to CEITEC S3 storage when:
1. MDDBR is unavailable (timeout/connection errors)
2. Files already exist on S3
3. Ground truth/metadata index exists for the entry

**Current State**: 
- MDDBR downloads are the ONLY source (100% failure rate when MDDBR is down)
- No S3 integration exists in BAT3 validation pipeline
- Ground truth metadata indexed separately (GroundTruthSignature table)
- Retry logic: 3 attempts, 30s timeout, then permanent failure

---

## Current Architecture Analysis

### File Download Flow (Current)
```
Queue Processor
    ↓
download_simulation_files(entry_id, local_accession, input_dir)
    ↓
1. Fetch filenotes from MDDBR (irb-dev.mddbr.eu)
   - Gets file metadata (filenames, sizes)
   - 30s timeout, 3 retries
    ↓
2. Download topology file (.prmtop/.top)
   - Direct MDDBR URL
   - 30s timeout
    ↓
3. Download trajectory file (.xtc/.dcd/.bin)
   - Direct MDDBR URL
   - 30s timeout
    ↓
4. Verify files exist
    ↓
5. Send to Celery for BAT3 validation
```

### Failure Points
```
❌ MDDBR timeout (60s per request × 3 retries = 180s per entry)
❌ No fallback mechanism
❌ Queue items stuck after 3 failures
❌ 100% dependency on MDDBR availability
```

### Metadata/Ground Truth State
```
GroundTruthSignature table contains:
  - entry_id (links to MddbEntry)
  - signature_type (uniprot, pdb, inchi, pubchem)
  - signature_value (actual identifier)
  - source_url (where fetched from)
  - raw_data (JSON response)
  - fetched_at (timestamp)

Key insight: If GroundTruthSignature exists for entry_id,
             metadata was successfully indexed → S3 files likely available
```

---

## S3 Fallback Architecture Options

### Option 1: S3 as Secondary Source (Recommended)
```
download_simulation_files():
    1. Try MDDBR first (primary source)
       ↓ (timeout/failure)
    2. Check if GroundTruthSignature exists for entry
       ↓ (exists)
    3. Construct S3 URL from local_accession
       ↓
    4. Download from S3
       ↓ (success)
    5. Continue validation
```

**Pros:**
- Minimal changes to existing flow
- MDDBR remains primary (authoritative)
- S3 only used when MDDBR fails
- Ground truth existence = reliable S3 indicator

**Cons:**
- Adds latency (MDDBR timeout before S3 attempt)
- Need S3 URL pattern discovery

---

### Option 2: S3-First with MDDBR Fallback
```
download_simulation_files():
    1. Check GroundTruthSignature exists
       ↓ (exists)
    2. Try S3 first
       ↓ (failure)
    3. Fall back to MDDBR
```

**Pros:**
- Faster when S3 available (no MDDBR timeout)
- Reduces load on MDDBR

**Cons:**
- S3 may have stale files
- MDDBR is authoritative source
- More complex logic

---

### Option 3: Parallel Download (MDDBR + S3 Race)
```
download_simulation_files():
    1. Start MDDBR download (async)
    2. If GroundTruthSignature exists, start S3 download (async)
    3. Use whichever completes first
    4. Cancel the other
```

**Pros:**
- Fastest possible download
- Automatic best-source selection

**Cons:**
- Wastes bandwidth (both downloads start)
- Complex async cancellation logic
- Over-engineered for current needs

---

## Key Considerations

### 1. S3 URL Pattern Discovery 🔍
**Unknown**: What's the S3 URL structure?

**Questions to Answer:**
- Base URL: `s3://ceitec-biodata/...` or `https://s3....`?
- Path pattern: `{local_accession}/{filename}` or `{entry_id}/{filename}`?
- Authentication: Public access? IAM role? Access keys?
- Region: EU-West? Specific endpoint?

**Discovery Needed:**
```python
# Need to find pattern like:
S3_BASE = "s3://ceitec-biodata-simulations/{local_accession}/"
# or
S3_URL = "https://s3.eu-west-1.amazonaws.com/ceitec-biodata/{local_accession}/{filename}"
```

---

### 2. File Integrity Verification ⚠️
**Risk**: S3 files may be:
- Outdated vs MDDBR
- Corrupted during upload
- Different versions

**Mitigation Strategies:**
```python
# Option A: Checksum verification
md5_s3 = get_s3_checksum(entry_id, filename)
md5_mddbr = get_mddbr_checksum(entry_id, filename)  # From filenotes
if md5_s3 != md5_mddbr:
    # S3 file is different - use MDDBR or flag for review

# Option B: File size verification
size_s3 = get_s3_file_size(entry_id, filename)
size_filenotes = filenotes[i]['size']
if size_s3 != size_filenotes:
    # Size mismatch - investigate

# Option C: Trust S3 if ground truth exists
# (simpler, assumes S3 upload was validated)
```

**Recommendation**: Start with **Option C** (trust S3), add checksums later if issues arise.

---

### 3. Ground Truth as S3 Availability Indicator ✅
**Current Logic**:
```python
# Check if ground truth exists
gt_exists = db.query(GroundTruthSignature).filter(
    GroundTruthSignature.entry_id == entry_id
).first() is not None

if gt_exists:
    # Safe to use S3 - metadata was indexed
    # Files should be on S3
else:
    # No ground truth - S3 may not have files
    # Must use MDDBR
```

**Assumption**: Ground truth indexing process also uploads files to S3.

**Validation Needed**: Confirm this assumption with the team managing the indexing pipeline.

---

### 4. Timeout Configuration ⏱️
**Current**: 30s MDDBR timeout (fails fast)

**With S3 Fallback**:
```python
# Option A: Keep 30s, then S3
MDDBR_TIMEOUT = 30  # Quick fail if MDDBR down
S3_TIMEOUT = 60     # S3 usually faster/more reliable

# Option B: Shorter MDDBR timeout
MDDBR_TIMEOUT = 15  # Even faster fail
S3_TIMEOUT = 60

# Option C: Configurable per-entry
# (based on file size from filenotes)
```

**Recommendation**: **Option A** - 30s is already deployed and working well.

---

### 5. Error Handling & Logging 📝
**New Error States**:
```python
# Current
- "Download failed" (generic)

# With S3
- "MDDBR timeout, trying S3..."
- "S3 download successful (fallback)"
- "S3 not available (no ground truth)"
- "S3 download failed"
- "Both MDDBR and S3 failed"
```

**Logging Requirements**:
```python
logger.info(f"MDDBR timeout after {timeout}s, checking S3 fallback...")
logger.info(f"Ground truth found for entry {entry_id}, attempting S3 download")
logger.info(f"Downloaded {filename} from S3 (fallback)")
logger.warning(f"S3 not available for entry {entry_id} (no ground truth)")
logger.error(f"Both MDDBR and S3 failed for entry {entry_id}")
```

---

### 6. Metrics & Monitoring 📊
**New Metrics to Track**:
```python
# Download source breakdown
- MDDBR_success_count
- S3_fallback_success_count
- S3_unavailable_count (no ground truth)
- Both_failed_count

# Performance
- MDDBR_avg_response_time
- S3_avg_response_time
- Fallback_latency_overhead

# Alerting
- Alert if S3 fallback rate > 20% (MDDBR having issues)
- Alert if both_failed > 5 in 1 hour
```

---

## Dangerous Bits / Risks ⚠️

### 1. Silent Data Divergence 🔴
**Risk**: S3 files differ from MDDBR files (different versions, corruption)

**Impact**: Validation results may not match ground truth

**Mitigation**:
- Add checksum verification (MD5/SHA256)
- Log when S3 is used vs MDDBR
- Periodic audit: compare random S3 vs MDDBR files

---

### 2. S3 Authentication Failures 🟡
**Risk**: S3 credentials expire or are misconfigured

**Impact**: Silent fallback failures, entries stuck

**Mitigation**:
- Use IAM roles (not access keys) for K8s pods
- Test S3 access on pod startup
- Alert on S3 authentication failures

---

### 3. Ground Truth ≠ S3 Files 🟡
**Risk**: Assumption wrong - ground truth exists but files not on S3

**Impact**: Wasted S3 lookup attempts, delayed failures

**Mitigation**:
- Add S3 existence check before download (HEAD request)
- Cache "S3 unavailable" per entry (don't retry)
- Monitor S3 404 rate

---

### 4. Increased Latency for MDDBR Failures 🟡
**Risk**: MDDBR timeout (30s) + S3 attempt = slower failure

**Impact**: Queue processing slower when MDDBR is down

**Mitigation**:
- Keep MDDBR timeout short (30s is good)
- S3 should be fast (<10s for typical files)
- Total worst case: 30s + 10s = 40s (acceptable)

---

### 5. S3 Cost Implications 🟢
**Risk**: S3 GET requests cost money

**Impact**: Minimal (CEITEC internal S3, likely no cost)

**Mitigation**:
- Confirm with CEITEC team
- Monitor S3 request volume
- Consider S3 lifecycle policies (archive old files)

---

## Implementation Plan

### Phase 1: S3 Integration Foundation (2-3 days)
**Tasks:**
1. **Discover S3 URL pattern**
   - Interview team managing mdfind indexing
   - Get S3 bucket name, region, access pattern
   - Test manual S3 download for known entry

2. **Add S3 client to BAT3**
   - Add `boto3` to requirements.txt
   - Create `s3_client.py` with download function
   - Add S3 config to `config.py` (bucket, region, endpoint)

3. **Add S3 availability check**
   - Function: `check_s3_files_exist(local_accession, filenames)`
   - Uses S3 HEAD Object (fast, no download)
   - Returns: True/False + file sizes

**Deliverables:**
- Working S3 download for test entry
- `s3_client.py` module
- Config options in `config.py`

---

### Phase 2: Fallback Logic (2-3 days)
**Tasks:**
1. **Modify `download_simulation_files()`**
   - Add MDDBR timeout handling
   - Check GroundTruthSignature existence
   - Attempt S3 download if MDDBR fails
   - Log which source was used

2. **Add error handling**
   - Distinguish MDDBR vs S3 failures
   - Proper retry logic for S3 (1-2 attempts)
   - Clear error messages

3. **Update queue processor**
   - Log when S3 fallback is used
   - Track source in ValidationQueue or Bat3Run

**Deliverables:**
- Working fallback logic
- Updated logging
- Source tracking

---

### Phase 3: Testing & Validation (2-3 days)
**Tasks:**
1. **Test scenarios**
   - MDDBR available → uses MDDBR ✅
   - MDDBR down, S3 available → uses S3 ✅
   - MDDBR down, no S3 → fails after retry ✅
   - Both available → uses MDDBR (primary) ✅

2. **Performance testing**
   - Measure MDDBR vs S3 download times
   - Measure fallback overhead
   - Verify no regression in success rate

3. **Ground truth verification**
   - Confirm GroundTruthSignature = S3 availability
   - Test entries with/without ground truth

**Deliverables:**
- Test results document
- Performance benchmarks
- Go/no-go decision

---

### Phase 4: Monitoring & Alerting (1-2 days)
**Tasks:**
1. **Add metrics**
   - Download source counters (MDDBR/S3)
   - Fallback success/failure rates
   - Average download times

2. **Add alerts**
   - High S3 fallback rate (>20%)
   - Both MDDBR and S3 failing
   - S3 authentication failures

3. **Dashboard updates**
   - Show download source breakdown
   - Show fallback statistics

**Deliverables:**
- Metrics in monitoring system
- Alerts configured
- Dashboard updates

---

## Configuration Changes Required

### config.py
```python
# S3 Configuration
S3_BUCKET = os.environ.get('S3_BUCKET', 'ceitec-biodata-simulations')
S3_REGION = os.environ.get('S3_REGION', 'eu-west-1')
S3_ENDPOINT = os.environ.get('S3_ENDPOINT', None)  # For custom S3-compatible storage
S3_USE_IAM = os.environ.get('S3_USE_IAM', 'true').lower() == 'true'
S3_ACCESS_KEY = os.environ.get('S3_ACCESS_KEY', None)
S3_SECRET_KEY = os.environ.get('S3_SECRET_KEY', None)

# S3 download timeout
S3_TIMEOUT = int(os.environ.get('S3_TIMEOUT', '60'))

# Fallback behavior
S3_FALLBACK_ENABLED = os.environ.get('S3_FALLBACK_ENABLED', 'true').lower() == 'true'
```

### Environment Variables (Kubernetes)
```yaml
env:
  - name: S3_BUCKET
    value: "ceitec-biodata-simulations"
  - name: S3_REGION
    value: "eu-west-1"
  - name: S3_USE_IAM
    value: "true"
  - name: S3_TIMEOUT
    value: "60"
  - name: S3_FALLBACK_ENABLED
    value: "true"
```

---

## Questions for the Team

### Critical (Block Implementation)
1. **What is the S3 bucket name and region?**
2. **What is the S3 URL/path pattern for simulation files?**
3. **How do we authenticate to S3 from K8s pods?**
4. **Does GroundTruthSignature existence guarantee files are on S3?**
5. **Who manages the S3 upload pipeline (to verify assumptions)?**

### Important (Should Know Before Phase 3)
6. **Are there file size limits on S3?**
7. **Is there S3 rate limiting we should be aware of?**
8. **Are there any compliance/security requirements for S3 access?**
9. **Should we verify checksums (MD5/SHA256) for S3 files?**
10. **Is there a cost tracking/monitoring system for S3?**

### Nice to Have
11. **Are there S3 lifecycle policies (archive/delete old files)?**
12. **Is there an S3 inventory/reporting system?**
13. **Should we cache S3 availability per entry (to avoid repeated HEAD requests)?**

---

## Recommendation

**Proceed with Option 1 (S3 as Secondary Source)**

**Rationale:**
- Minimal risk (MDDBR remains primary)
- Clear fallback path (MDDBR → check ground truth → S3)
- Easy to implement and test
- Can be disabled via config if issues arise
- Addresses current pain point (MDDBR downtime)

**Timeline**: 7-11 days total (Phases 1-4)

**Success Criteria:**
- <5% of downloads use S3 fallback (MDDBR usually available)
- 95%+ success rate when MDDBR is down (S3 saves the day)
- No increase in validation errors
- No performance regression

---

## Next Steps

1. **Schedule meeting with mdfind team** (critical for Phase 1)
   - Get S3 details (bucket, path, auth)
   - Verify ground truth → S3 assumption
   - Get test entries with known S3 files

2. **Create proof-of-concept branch**
   - Implement Phase 1 (S3 client)
   - Test with 1-2 known entries
   - Demo to team

3. **Decision point**: After Phase 1 demo
   - Proceed with full implementation?
   - Adjust approach based on findings?
   - Pause if S3 not viable?

---

**Document Version**: 1.0  
**Created**: 2026-08-10  
**Status**: Ready for review

---

## ⚠️ **CRITICAL UPDATE: MDDB Access Constraint**

**Important**: The team has indicated that:

1. **`example_mdfind` folder** will be provided (not yet present in workspace)
2. **Contains a read-only script** for querying the MDDB database
3. **This script is the ONLY approved way** to interact with MDDB
4. **No direct API calls or database connections** allowed

### **Impact on Architecture**

This constraint **significantly changes** the implementation approach:

#### **Original Assumption** ❌
```python
# Direct MDDBR API calls
response = requests.get(f"https://irb-dev.mddbr.eu/api/rest/v1/projects/{local_accession}/filenotes")
```

#### **New Reality** ✅
```python
# Must use provided read-only script
result = subprocess.run(
    ['/path/to/mdfind_script.py', '--query', local_accession],
    capture_output=True,
    text=True
)
filenotes = json.loads(result.stdout)
```

### **Revised Architecture**

```
download_simulation_files():
    1. Try MDDB via read-only script
       ↓ (timeout/failure)
    2. Check GroundTruthSignature exists
       ↓ (exists)
    3. Download from S3
       ↓ (success)
    4. Continue validation
```

### **New Questions for the Team**

**Critical (Block Implementation):**
1. **Where is the read-only script located?** (path in container/host)
2. **What is the script's interface?** (CLI args, stdin/stdout format?)
3. **What queries does it support?** (filenotes, file downloads, metadata?)
4. **Can it download files or only return metadata?**
5. **What is the script's timeout behavior?**
6. **Does it support batch queries or one entry at a time?**
7. **How does it handle errors/timeouts?**

**Integration Questions:**
8. **Does the script need database credentials?** (env vars, config file?)
9. **Can it run from K8s pods?** (network access to MDDB?)
10. **What is the expected response format?** (JSON, CSV, text?)
11. **Are there rate limits on script usage?**
12. **Does it cache results or query live DB every time?**

### **Revised Phase 1 Tasks**

**Before any S3 work, need to:**

1. **Get the read-only script**
   - Location: `example_mdfind/` folder
   - Test basic functionality
   - Understand query interface

2. **Test script with known entries**
   - Query for entries we know exist
   - Verify response format
   - Test timeout behavior

3. **Understand S3 references in script output**
   - Does script return S3 paths/URLs?
   - Or only MDDBR URLs?
   - Can we infer S3 availability from script output?

4. **Integration prototype**
   - Call script from Python (subprocess or import)
   - Parse response
   - Handle errors/timeouts

### **Revised Timeline**

**Add 2-3 days to Phase 1** for:
- Understanding the script interface
- Testing with real entries
- Building wrapper functions
- Error handling integration

**Total Phase 1**: 4-6 days (was 2-3 days)

### **Risk Assessment**

**New Risks:**
- 🟡 Script may be slower than direct API calls
- 🟡 Script may not support all queries we need
- 🟡 Script output format may be hard to parse
- 🟡 Script may have different timeout/retry behavior
- 🔴 Script may not be available in K8s environment

**Mitigation:**
- Test script thoroughly before implementation
- Build robust wrapper with error handling
- Have fallback to direct MDDBR API if script unavailable
- Document script limitations clearly

---

**Updated**: 2026-08-10  
**Status**: Waiting for `example_mdfind` folder with read-only script
