#!/usr/bin/env bash
# Usage: ./scripts/k8s/delete-job.sh [--force]
#
# Delete the bat3-blast-db-download job.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "${SCRIPT_DIR}/common.sh"

JOB_NAME="bat3-blast-db-download"
FORCE=false

show_help() {
    cat <<HELP
Usage: $(basename "$0") [--force]

Delete the bat3-blast-db-download job and any associated pods.

Options:
  --force     Force-delete stuck pods (with --grace-period=0)
  -h, --help  Show this help message

Examples:
  $(basename "$0")          # Graceful delete
  $(basename "$0") --force  # Force delete stuck pods
HELP
}

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --force)
            FORCE=true
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Unknown argument '$arg'"
            show_help
            exit 1
            ;;
    esac
done

# Resolve namespace
NAMESPACE="${NAMESPACE:-$(resolve_namespace)}"
if [[ -z "$NAMESPACE" ]]; then
    echo "Error: Could not detect namespace. Set NAMESPACE env var or ensure bat3-worker pods exist."
    exit 1
fi

echo "Namespace: $NAMESPACE"
echo "Job name: $JOB_NAME"
echo "Force mode: $FORCE"
echo ""

# Check if job exists
if ! ${KUBECTL} -n "$NAMESPACE" get job "$JOB_NAME" &>/dev/null; then
    echo "Job '$JOB_NAME' not found in namespace '$NAMESPACE'."
    echo "Nothing to delete."
    exit 0
fi

# List associated pods before deletion
echo "Associated pods:"
${KUBECTL} -n "$NAMESPACE" get pods -l "job-name=$JOB_NAME" --no-headers 2>/dev/null || echo "  (none found)"
echo ""

# Delete the job
echo "Deleting job..."
if [[ "$FORCE" == "true" ]]; then
    print_kubectl -n "$NAMESPACE" delete job "$JOB_NAME" --grace-period=0 --force
    ${KUBECTL} -n "$NAMESPACE" delete job "$JOB_NAME" --grace-period=0 --force
else
    print_kubectl -n "$NAMESPACE" delete job "$JOB_NAME"
    ${KUBECTL} -n "$NAMESPACE" delete job "$JOB_NAME"
fi

# Delete any orphaned pods with the job label
echo ""
echo "Cleaning up orphaned pods..."
ORPHAN_PODS=$(${KUBECTL} -n "$NAMESPACE" get pods -l "job-name=$JOB_NAME" --no-headers -o name 2>/dev/null || true)

if [[ -n "$ORPHAN_PODS" ]]; then
    for pod in $ORPHAN_PODS; do
        echo "Deleting $pod..."
        if [[ "$FORCE" == "true" ]]; then
            ${KUBECTL} -n "$NAMESPACE" delete "$pod" --grace-period=0 --force
        else
            ${KUBECTL} -n "$NAMESPACE" delete "$pod"
        fi
    done
else
    echo "No orphaned pods found."
fi

# Verify deletion
echo ""
echo "Verifying deletion..."
sleep 2

if ${KUBECTL} -n "$NAMESPACE" get job "$JOB_NAME" &>/dev/null; then
    echo "Warning: Job still exists after deletion."
else
    echo "Job successfully deleted."
fi

REMAINING_PODS=$(${KUBECTL} -n "$NAMESPACE" get pods -l "job-name=$JOB_NAME" --no-headers 2>/dev/null || true)
if [[ -n "$REMAINING_PODS" ]]; then
    echo "Warning: Some pods still remain:"
    echo "$REMAINING_PODS"
else
    echo "All associated pods cleaned up."
fi

echo ""
echo "Done."
