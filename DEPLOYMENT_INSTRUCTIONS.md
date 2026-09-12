# Failure Analysis Tool - DEPLOYMENT TO CEITEC

**Date**: 2026-08-10  
**Status**: Ready to Deploy

---

## 📊 Current Status

```
Total Failed Runs: 263 (NOT 100 - fixed the query!)
  - Hung before completion: 172 🔴
  - Completed with errors: 91
  - Network timeouts: 150
  - Download failures: 21
  - Code bugs: 1 (fixed)
```

---

## 🚀 Deployment Steps for CEITEC

### **Step 1: Copy Files to CEITEC Server**

```bash
# From your local machine
scp /home/tomsko/work/bat3/api/failure_analysis.py \
    user@bioid.dyn.cloud.e-infra.cz:/path/to/bat3/api/

scp /home/tomsko/work/bat3/web/src/Pages/FailureAnalysis.tsx \
    user@bioid.dyn.cloud.e-infra.cz:/path/to/bat3/web/src/Pages/

scp /home/tomsko/work/bat3/DEPLOYMENT_INSTRUCTIONS.md \
    user@bioid.dyn.cloud.e-infra.cz:/tmp/
```

### **Step 2: SSH to CEITEC Server**

```bash
ssh user@bioid.dyn.cloud.e-infra.cz
cd /path/to/bat3
```

### **Step 3: Add API Route to main.py**

Edit `/path/to/bat3/main.py` and add at the end (after line 1948):

```python
# =============================================================================
# FAILURE ANALYSIS API
# =============================================================================

@app.get("/api/failure-analysis")
async def get_failure_analysis():
    """
    Analyze failure patterns across ALL failed validation runs.
    Returns comprehensive statistics and recommendations.
    """
    import sys
    sys.path.insert(0, '/path/to/bat3')
    
    from api.failure_analysis import analyze_failures_api
    
    try:
        results = analyze_failures_api(file_limit=500)
        return results
    except Exception as e:
        return {"error": str(e), "analyzed_at": datetime.utcnow().isoformat()}
```

### **Step 4: Add Frontend Route**

Edit `/path/to/bat3/web/src/App.tsx`:

**Add import** (line 8, after AnnotationResults import):
```tsx
import FailureAnalysis from './Pages/FailureAnalysis';
```

**Add route** (in the Routes section, after AnnotationResults):
```tsx
<Route path="/failure-analysis" element={<FailureAnalysis />} />
```

### **Step 5: Build Frontend**

```bash
cd /path/to/bat3/web
npm run build
```

### **Step 6: Restart Backend** (if needed)

```bash
# Depending on your deployment setup
systemctl restart bat3-backend
# OR
docker restart bat3-backend
# OR
pm2 restart bat3-backend
```

---

## ✅ Verification

### **Test API**
```bash
curl https://bioid.dyn.cloud.e-infra.cz/api/failure-analysis | python -m json.tool
```

Expected output:
```json
{
  "analyzed_at": "2026-08-10T...",
  "database": {
    "total_failed_runs": 263,
    "with_results_json": 91,
    "without_results_json": 172,
    ...
  },
  ...
}
```

### **Test Frontend**
```
Open in browser: https://bioid.dyn.cloud.e-infra.cz/failure-analysis
```

You should see:
- "Failure Analysis" header
- "Run Analysis" button
- Statistics cards showing 263 total failures
- Error categories breakdown
- Recommendations

---

## 📁 Files to Deploy

| File | Destination | Purpose |
|------|-------------|---------|
| `api/failure_analysis.py` | `/path/to/bat3/api/` | Analysis engine |
| `web/src/Pages/FailureAnalysis.tsx` | `/path/to/bat3/web/src/Pages/` | React component |
| `main.py` (modified) | `/path/to/bat3/` | Add API route |
| `web/src/App.tsx` (modified) | `/path/to/bat3/web/src/` | Add frontend route |

---

## 🔍 What It Will Show

Once deployed, the tool will analyze all **263 failed runs** and display:

### **Summary**
- Total Failed Runs: **263**
- Hung (No Results): **172** 🔴
- Completed w/ Errors: **91**

### **Error Categories**
1. Network/Timeout: ~150
2. Other: ~90
3. Download Failure: ~21
4. Code bug: 1

### **Recommendations**
1. 🔴 CRITICAL: 172 runs hung - BAT3 executor hanging
2. 🟡 Network issues: 150 timeouts
3. 📥 Download failures: 21 (mdfind will help)

---

## 🎯 Access After Deployment

**Frontend**: https://bioid.dyn.cloud.e-infra.cz/failure-analysis  
**API**: https://bioid.dyn.cloud.e-infra.cz/api/failure-analysis

---

**Ready to deploy!** All files are in `/home/tomsko/work/bat3/`

