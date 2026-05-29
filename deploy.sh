#!/usr/bin/env bash
set -euo pipefail

COMPONENT="all"
BUILD=false
NAMESPACE="${BAT3_NAMESPACE:-gromacs-bioid-ns}"
REGISTRY="${BAT3_REGISTRY:-cerit.io/tomsko}"
TAG="${BAT3_TAG:-latest}"
SERVER_NAME="$(grep '^servername:' bat3-chart/values.yaml 2>/dev/null | awk '{print $2}' || echo 'unknown')"

usage() {
    echo "Usage: $0 [all|backend|api|worker|frontend] [--build] [-n namespace]"
    echo ""
    echo "Components:"
    echo "  all       - Deploy full stack via Helm"
    echo "  backend   - Restart API + Worker deployments"
    echo "  api       - Restart API deployment"
    echo "  worker    - Restart Worker deployment"
    echo "  frontend  - Restart Frontend (web) deployment"
    echo ""
    echo "Options:"
    echo "  --build   - Build and push Docker images first"
    echo "  -n        - Kubernetes namespace (default: $NAMESPACE)"
    exit 1
}

check_old_release() {
    local old_release="gmx-bioid"
    local ns="$NAMESPACE"
    if helm list -n "$ns" -q 2>/dev/null | grep -qx "$old_release"; then
        echo "⚠️  Old release '$old_release' still exists in namespace '$ns'."
        echo "   It owns the ingress host \"$SERVER_NAME\" which conflicts with BAT3."
        echo ""
        echo "   Options:"
        echo "   1. Uninstall the old release (this will also remove its PVCs and data):"
        echo "      helm uninstall $old_release -n $ns"
        echo ""
        echo "   2. Or deploy BAT3 with a different ingress host (edit bat3-chart/values.yaml)"
        echo ""
        echo "   After resolving, re-run: $0 all"
        exit 1
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --build)
            BUILD=true
            shift
            ;;
        -n|--namespace)
            shift
            NAMESPACE="$1"
            shift
            ;;
        -h|--help)
            usage
            ;;
        all|backend|api|worker|frontend)
            COMPONENT="$1"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

echo "🚀 BAT3 Deploy"
echo "   Component: $COMPONENT"
echo "   Namespace: $NAMESPACE"
echo "   Build:     $BUILD"
echo "   Tag:       $TAG"
echo ""

build_and_push() {
    local name=$1
    local dockerfile=$2
    local tag="$REGISTRY/bat3-$name:$TAG"
    echo "🔨 Building $tag ..."
    DOCKER_BUILDKIT=0 docker build --network=host -t "$tag" -f "$dockerfile" .
    echo "📤 Pushing $tag ..."
    docker push "$tag"
    echo "✅ $tag ready"
}

wait_for_pods() {
    local ns="$1"
    local max_wait=120
    local waited=0
    echo "⏳ Waiting for pods to be ready..."
    while [[ $waited -lt $max_wait ]]; do
        api_ready=$(kubectl get pods -n "$ns" -l app=bat3-bat3-api --no-headers 2>/dev/null | grep -c "Running" || true)
        worker_ready=$(kubectl get pods -n "$ns" -l app=bat3-bat3-worker --no-headers 2>/dev/null | grep -c "Running" || true)
        web_ready=$(kubectl get pods -n "$ns" -l app=bat3-bat3-web --no-headers 2>/dev/null | grep -c "Running" || true)
        if [[ "$api_ready" -ge 1 && "$worker_ready" -ge 1 && "$web_ready" -ge 1 ]]; then
            echo "✅ All pods are Running!"
            return 0
        fi
        sleep 5
        waited=$((waited + 5))
    done
    echo "⚠️ Timed out waiting for pods. Check status with: kubectl get pods -n $ns"
    return 1
}

if [[ "$BUILD" == "true" ]]; then
    case "$COMPONENT" in
        all)
            build_and_push api Dockerfile.api
            build_and_push worker Dockerfile.worker
            build_and_push frontend Dockerfile.frontend
            ;;
        backend)
            build_and_push api Dockerfile.api
            build_and_push worker Dockerfile.worker
            ;;
        api)
            build_and_push api Dockerfile.api
            ;;
        worker)
            build_and_push worker Dockerfile.worker
            ;;
        frontend)
            build_and_push frontend Dockerfile.frontend
            ;;
        *)
            echo "❌ Unknown component: $COMPONENT"
            usage
            ;;
    esac
    echo ""
fi

case "$COMPONENT" in
    all)
        check_old_release
        echo "📦 Running Helm upgrade for full stack..."
        helm upgrade --install bat3 ./bat3-chart \
            --namespace "$NAMESPACE" \
            --create-namespace \
            --set "image.api.tag=$TAG" \
            --set "image.worker.tag=$TAG" \
            --set "image.web.tag=$TAG"
        echo "✅ Helm upgrade done!"
        echo ""
        echo "🔄 Restarting deployments to force fresh image pulls..."
        kubectl rollout restart deployment "bat3-bat3-api" -n "$NAMESPACE"
        kubectl rollout restart deployment "bat3-bat3-worker" -n "$NAMESPACE"
        kubectl rollout restart deployment "bat3-bat3-web" -n "$NAMESPACE"
        wait_for_pods "$NAMESPACE"
        echo "✅ Full stack deployed!"
        ;;
    backend)
        echo "🔄 Restarting API and Worker deployments..."
        kubectl rollout restart deployment "bat3-bat3-api" -n "$NAMESPACE"
        kubectl rollout restart deployment "bat3-bat3-worker" -n "$NAMESPACE"
        wait_for_pods "$NAMESPACE"
        echo "✅ Backend restarted!"
        ;;
    api)
        echo "🔄 Restarting API deployment..."
        kubectl rollout restart deployment "bat3-bat3-api" -n "$NAMESPACE"
        wait_for_pods "$NAMESPACE"
        echo "✅ API restarted!"
        ;;
    worker)
        echo "🔄 Restarting Worker deployment..."
        kubectl rollout restart deployment "bat3-bat3-worker" -n "$NAMESPACE"
        wait_for_pods "$NAMESPACE"
        echo "✅ Worker restarted!"
        ;;
    frontend)
        echo "🔄 Restarting Frontend deployment..."
        kubectl rollout restart deployment "bat3-bat3-web" -n "$NAMESPACE"
        wait_for_pods "$NAMESPACE"
        echo "✅ Frontend restarted!"
        ;;
    *)
        echo "❌ Unknown component: $COMPONENT"
        usage
        ;;
esac
