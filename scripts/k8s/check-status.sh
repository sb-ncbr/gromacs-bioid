#!/usr/bin/env bash
# Usage: ./scripts/k8s/check-status.sh
#
# Print status dashboard:
#   - Namespace
#   - Deployments (replicas, status)
#   - Running pods
#   - PVCs (size, status, used %)
#   - Resource quota usage
#   - Recent events

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "${SCRIPT_DIR}/common.sh"

show_help() {
    cat <<HELP
Usage: $(basename "$0")

Print a dashboard of deployment health including:
  - Namespace
  - Deployments (replicas, status)
  - Running pods
  - PVCs (size, status)
  - Resource quota usage
  - Recent events

Options:
  -h, --help  Show this help message
HELP
}

# Parse arguments
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    show_help
    exit 0
fi

# Resolve namespace
NAMESPACE="${NAMESPACE:-$(resolve_namespace)}"
if [[ -z "$NAMESPACE" ]]; then
    echo "Error: Could not detect namespace. Set NAMESPACE env var or ensure bat3-worker pods exist."
    exit 1
fi

echo "=============================================="
echo "         BAT3 Kubernetes Status Dashboard    "
echo "=============================================="
echo ""
echo "Namespace: $NAMESPACE"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

echo "----------------------------------------------"
echo "DEPLOYMENTS"
echo "----------------------------------------------"
${KUBECTL} -n "$NAMESPACE" get deployments -o wide 2>/dev/null || echo "  No deployments found"
echo ""

echo "----------------------------------------------"
echo "PODS"
echo "----------------------------------------------"
${KUBECTL} -n "$NAMESPACE" get pods -o wide 2>/dev/null || echo "  No pods found"
echo ""

echo "----------------------------------------------"
echo "PERSISTENT VOLUME CLAIMS"
echo "----------------------------------------------"
${KUBECTL} -n "$NAMESPACE" get pvc -o wide 2>/dev/null || echo "  No PVCs found"
echo ""

# Show PVC details if any exist
PVC_LIST=$(${KUBECTL} -n "$NAMESPACE" get pvc -o name 2>/dev/null || true)
if [[ -n "$PVC_LIST" ]]; then
    echo "PVC Details:"
    for pvc in $PVC_LIST; do
        PVC_NAME=$(echo "$pvc" | cut -d'/' -f2)
        echo ""
        echo "  $PVC_NAME:"
        ${KUBECTL} -n "$NAMESPACE" get "$pvc" -o jsonpath='    Storage Class: {.spec.storageClassName}{"\n"}    Access Modes: {.spec.accessModes[*]}{"\n"}    Capacity: {.status.capacity.storage}{"\n"}    Status: {.status.phase}{"\n"}' 2>/dev/null || echo "    (unable to get details)"
    done
    echo ""
fi

echo "----------------------------------------------"
echo "RESOURCE QUOTAS"
echo "----------------------------------------------"
${KUBECTL} -n "$NAMESPACE" get resourcequotas -o wide 2>/dev/null || echo "  No resource quotas found"
echo ""

# Show quota details if any exist
QUOTA_LIST=$(${KUBECTL} -n "$NAMESPACE" get resourcequotas -o name 2>/dev/null || true)
if [[ -n "$QUOTA_LIST" ]]; then
    for quota in $QUOTA_LIST; do
        QUOTA_NAME=$(echo "$quota" | cut -d'/' -f2)
        echo "  $QUOTA_NAME:"
        ${KUBECTL} -n "$NAMESPACE" get "$quota" -o jsonpath='    Used: {.status.used}{"\n"}    Hard: {.status.hard}{"\n"}' 2>/dev/null || echo "    (unable to get details)"
    done
    echo ""
fi

echo "----------------------------------------------"
echo "RECENT EVENTS (last 20)"
echo "----------------------------------------------"
${KUBECTL} -n "$NAMESPACE" get events --sort-by='.lastTimestamp' 2>/dev/null | tail -20 || echo "  No events found"
echo ""

echo "----------------------------------------------"
echo "JOBS"
echo "----------------------------------------------"
${KUBECTL} -n "$NAMESPACE" get jobs -o wide 2>/dev/null || echo "  No jobs found"
echo ""

echo "=============================================="
echo "End of Status Dashboard"
echo "=============================================="
