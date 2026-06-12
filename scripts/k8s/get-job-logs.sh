#!/usr/bin/env bash
# Usage: ./scripts/k8s/get-job-logs.sh [--follow] [--previous]
#
# Get logs from the blast-db-download job.
# Default: prints last 100 lines.
# --follow: stream in real-time.
# --previous: get logs from the previous failed pod instance.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "${SCRIPT_DIR}/common.sh"

JOB_NAME="bat3-blast-db-download"
FOLLOW=false
PREVIOUS=false
LINES=100

show_help() {
    cat <<HELP
Usage: $(basename "$0") [--follow] [--previous] [--lines N]

Get logs from the bat3-blast-db-download job pod.

Options:
  --follow, -f    Stream logs in real-time (like tail -f)
  --previous, -p  Get logs from previous failed pod instance
  --lines N, -n N Number of lines to show (default: 100)
  -h, --help      Show this help message

Examples:
  $(basename "$0")              # Last 100 lines
  $(basename "$0") -f           # Follow logs in real-time
  $(basename "$0") -p           # Logs from previous failed attempt
  $(basename "$0") -f -p        # Follow previous instance logs
HELP
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -p|--previous)
            PREVIOUS=true
            shift
            ;;
        -n|--lines)
            LINES="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Unknown argument '$1'"
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
echo ""

# Find the most recent pod for this job
POD_NAME=""
POD_NAME=$(${KUBECTL} -n "$NAMESPACE" get pods -l "job-name=$JOB_NAME" --sort-by='.metadata.creationTimestamp' -o jsonpath='{.items[-1].metadata.name}' 2>/dev/null || true)

if [[ -z "$POD_NAME" ]]; then
    echo "Error: No pods found for job '$JOB_NAME' in namespace '$NAMESPACE'."
    echo ""
    echo "The job may not have been run yet, or all pods have been deleted."
    echo "Run the download job first, or check with:"
    echo "  ${KUBECTL} -n $NAMESPACE get pods -l job-name=$JOB_NAME"
    exit 1
fi

echo "Pod: $POD_NAME"
echo ""

# Build kubectl logs command
LOG_CMD="${KUBECTL} -n $NAMESPACE logs $POD_NAME --tail=$LINES"

if [[ "$PREVIOUS" == "true" ]]; then
    LOG_CMD="$LOG_CMD --previous"
fi

if [[ "$FOLLOW" == "true" ]]; then
    LOG_CMD="$LOG_CMD -f"
fi

echo "Streaming logs..."
echo "---"

# Execute logs command
eval "$LOG_CMD"
