# Failure Analysis Tool

**Date**: 2026-08-10  
**Status**: ✅ Complete

---

## 🎯 Overview

Comprehensive failure analysis tool that investigates where BAT3 validation pipeline is failing by analyzing both database records and results.json files.

---

## 🔍 What It Does

1. **Checks Database** - Finds all runs marked as "failed" in bat3_runs table
2. **Analyzes results.json** - For runs that completed enough to write results
3. **Identifies Patterns** - Aggregates failures by task, error type, and failure point
4. **Generates Recommendations** - Actionable insights based on failure patterns

---

## 📊 Key Findings (Current Analysis)

```
Database Failures: 100
  - With results.json: 1 (completed but had errors)
  - Without results.json: 99 (HUNG before completion) 🔴

Error Categories:
  - Network/Timeout: 96 (MDDBR was down in July)
  - Download Failure: 2
  - Code bug: 1 (local_accession bug - FIXED)
  - Cancelled: 1

CRITICAL: 99 runs hung before writing results.json
→ BAT3 executor is hanging during analysis
```

---

## 🛠️ Components Created

### **1. API Endpoint**
- **Location**: `/api/failure-analysis`
- **File**: `api/failure_analysis.py`
- **Method**: GET
- **Returns**: Comprehensive failure analysis JSON

### **2. Frontend Tab**
- **Location**: `/failure-analysis.html`
- **Features**:
  - One-click analysis button
  - Visual statistics dashboard
  - Error category breakdown
  - Task failure visualization
  - Actionable recommendations
  - Raw data export

### **3. Integration**
- **Backend**: `main.py` (line 1948)
- **Frontend**: Accessible at `http://localhost:8000/failure-analysis.html`

---

## 📈 API Response Structure

```json
{
  "analyzed_at": "2026-08-10T20:47:00.000000",
  "database": {
    "total_failed_runs": 100,
    "with_results_json": 1,
    "without_results_json": 99,
    "error_categories": {
      "Network/Timeout": 96,
      "Download Failure": 2,
      ...
    },
    "recent_failures": [...]
  },
  "results_files": {
    "runs_analyzed": 50,
    "task_failures": {...},
    "failure_points": {...}
  },
  "summary": {
    "total_db_failures": 100,
    "hung_before_completion": 99,
    "most_common_error_category": ["Network/Timeout", 96],
    ...
  },
  "recommendations": [
    "🔴 CRITICAL: 99 runs hung before writing results.json...",
    "🟡 Network issues: 96 failures...",
    ...
  ]
}
```

---

## 🚀 Usage

### **Via API**
```bash
curl http://localhost:8000/api/failure-analysis | python -m json.tool
```

### **Via Frontend**
1. Open `http://localhost:8000/failure-analysis.html`
2. Click "Run Analysis" button
3. View interactive dashboard

### **Programmatically**
```python
from api.failure_analysis import analyze_failures_api

results = analyze_failures_api(db_limit=100, file_limit=200)
print(f"Hung runs: {results['database']['without_results_json']}")
print(f"Top error: {results['summary']['most_common_error_category']}")
```

---

## 🔧 Configuration

```python
# Adjust limits for analysis
analyze_failures_api(
    db_limit=100,      # Max failed runs from database
    file_limit=200     # Max results.json files to analyze
)
```

---

## 📋 BAT3 Task Structure

The analysis tracks these BAT3 pipeline tasks:

| Task | Description |
|------|-------------|
| `discover_input` | Find and identify input files |
| `load_simulation` | Load trajectory/topology |
| `repair_topology` | Fix missing atoms/bonds |
| `unwrap_periodic_boundaries` | Handle PBC |
| `analyze_universe` | Extract molecular info |
| `generate_signatures` | Create structural signatures |
| `identify_molecules` | Match to databases |
| `summarize_segments` | Aggregate results |
| `export_mmcif` | Write output files |

---

## 🎯 Current Issues Identified

### **CRITICAL: Executor Hanging** 🔴
- **99 runs** hung before writing results.json
- BAT3 executor never completes
- Likely infinite loop or deadlock in analysis tasks
- **Action needed**: Add timeouts, debug hanging tasks

### **Network Timeouts** 🟡
- **96 failures** from July when MDDBR was down
- **Solution**: mdfind fallback (already implemented)

### **Download Failures** 🟡
- **2 failures** downloading files
- **Solution**: mdfind fallback will help

---

## 🔍 Next Steps

1. **Debug Hanging Executor**
   - Add timeout to BAT3 executor
   - Log which task is hanging
   - Check for infinite loops in signature generation

2. **Monitor New Failures**
   - Run analysis daily
   - Track if hung count increases
   - Identify new error patterns

3. **Implement Recommendations**
   - Add executor timeout
   - Increase network timeouts
   - Fix known code bugs

---

## 📚 Files Created

| File | Purpose |
|------|---------|
| `api/failure_analysis.py` | Analysis logic |
| `web/failure-analysis.html` | Frontend dashboard |
| `main.py` (line 1948) | API endpoint |
| `docs/FAILURE_ANALYSIS_TOOL.md` | This documentation |

---

**Ready to use!** Access at: `http://localhost:8000/failure-analysis.html`

