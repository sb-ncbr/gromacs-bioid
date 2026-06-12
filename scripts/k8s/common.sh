#!/usr/bin/env bash
# Source this file: . scripts/k8s/common.sh
# Shared constants and functions for all k8s helper scripts

set -euo pipefail

# Kubectl configuration — override via env vars
KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"
KUBECTL="kubectl --kubeconfig ${KUBECONFIG}"

# Auto-detect namespace from running bat3 worker pods
detect_namespace() {
    local ns
    ns=$(${KUBECTL} get pods --all-namespaces -l app=bat3-worker -o jsonpath='{.items[0].metadata.namespace}' 2>/dev/null || true)
    echo "$ns"
}

# Auto-detect deployment name
detect_worker_deployment() {
    local dep
    dep=$(${KUBECTL} -n "$NAMESPACE" get deployments -o jsonpath='{.items[?(@.metadata.name=~".*-worker")].metadata.name}' 2>/dev/null | awk '{print $1}')
    echo "$dep"
}

# Auto-detect release name from deployment
detect_release_name() {
    local dep="$1"
    # Strip "-worker" suffix
    echo "${dep%-worker}"
}

# Resolve namespace (env var > auto-detect > default)
resolve_namespace() {
    if [[ -n "${NAMESPACE:-}" ]]; then
        echo "$NAMESPACE"
        return
    fi
    local detected
    detected=$(detect_namespace)
    if [[ -n "$detected" ]]; then
        echo "$detected"
        return
    fi
    echo "default"
}

# Print kubectl command that would be run
print_kubectl() {
    echo "  $KUBECTL $*"
}

# Get script directory for relative paths
get_script_dir() {
    cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
}
