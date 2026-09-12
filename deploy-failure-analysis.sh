#!/bin/bash
# Deployment script for Failure Analysis Tool
# Deploy to ceitec-biodata-ns (development namespace where validation runs)

set -e

echo "=========================================="
echo "Failure Analysis Tool Deployment"
echo "Namespace: ceitec-biodata-ns (development)"
echo "=========================================="
echo ""

BAT3_DIR="/home/tomsko/work/bat3"
cd "$BAT3_DIR"

# Step 1: Verify files exist
echo "[1/6] Verifying files..."
for file in "api/failure_analysis.py" "web/src/Pages/FailureAnalysis.tsx" "web/src/Components/Header.tsx"; do
    if [ ! -f "$file" ]; then
        echo "❌ Missing: $file"
        exit 1
    fi
done
echo "     ✓ All files present"

# Step 2: Add API route to main.py
echo "[2/6] Adding API route to main.py..."
if grep -q "failure-analysis" main.py; then
    echo "     ✓ API route already exists"
else
    cat >> main.py << 'ENDROUTE'

# =============================================================================
# FAILURE ANALYSIS API
# =============================================================================

@app.get("/api/failure-analysis")
async def get_failure_analysis():
    from api.failure_analysis import analyze_failures_api
    return analyze_failures_api(file_limit=500)
ENDROUTE
    echo "     ✓ API route added"
fi

# Step 3: Add frontend import to App.tsx
echo "[3/6] Adding frontend import..."
if grep -q "FailureAnalysis" web/src/App.tsx; then
    echo "     ✓ Import already exists"
else
    sed -i '/import AnnotationResults/a import FailureAnalysis from '\''./Pages/FailureAnalysis'\'';' web/src/App.tsx
    echo "     ✓ Import added"
fi

# Step 4: Add frontend route to App.tsx
echo "[4/6] Adding frontend route..."
if grep -q "failure-analysis" web/src/App.tsx; then
    echo "     ✓ Route already exists"
else
    sed -i '/AnnotationResults \/>/a \                <Route path="/failure-analysis" element={<FailureAnalysis />} />' web/src/App.tsx
    echo "     ✓ Route added"
fi

# Step 5: Build frontend
echo "[5/6] Building frontend..."
cd web
npm run build
echo "     ✓ Frontend built"

# Step 6: Restart backend in ceitec-biodata-ns namespace
echo "[6/6] Restarting backend in ceitec-biodata-ns namespace..."
cd "$BAT3_DIR"

if command -v kubectl &> /dev/null; then
    kubectl rollout restart deployment bat3-backend -n ceitec-biodata-ns 2>/dev/null && \
        echo "     ✓ Backend restarted (kubectl - ceitec-biodata-ns)" || \
        echo "     ⚠ kubectl restart failed - manual restart may be needed"
elif command -v systemctl &> /dev/null && systemctl is-active --quiet bat3-backend; then
    sudo systemctl restart bat3-backend
    echo "     ✓ Backend restarted (systemctl)"
else
    echo "     ⚠ Manual restart required"
    echo "     Run: kubectl rollout restart deployment bat3-backend -n ceitec-biodata-ns"
fi

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "Access the tool at:"
echo "  https://bioid-validation.dyn.cloud.e-infra.cz/failure-analysis"
echo ""
echo "Or click the 📊 icon in the header on:"
echo "  https://bioid-validation.dyn.cloud.e-infra.cz/"
echo ""
echo "Namespace: ceitec-biodata-ns (development)"
echo "Analyzing: 263 failed validation runs"
echo ""
echo "=========================================="
