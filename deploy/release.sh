#!/bin/bash
# BioID release (production: namespace ceitec-biodata-ns). Since 2026-11-17
# this script and deploy/live/*.yaml are how BioID is deployed; the helm
# chart (bat3-chart/) is retired and refuses to render.
#
# Usage (any combination, at least one):
#   deploy/release.sh --backend <sha256:digest> --code <git short sha> \
#                     [--web <frontend tag>] [--docs <docs tag>] [--mcp <mcp tag>]
#
#   --backend  API, fleet, UI and repository workers (one image). Refused while
#              any queue holds work or a run is active: restarted workers
#              kill running runs. Pause submitters first (mdval) and wait.
#   --allow-repository  with --backend: the repository queue (campaigns) may
#              hold work and its runs are interrupted (with automatic retries
#              on, they run again); the web queue must still be idle
#   --web      the web frontend (bat3-frontend:<tag>); no queue check needed
#   --docs     the documentation site (bat3-docs:<tag>)
#   --mcp      the MCP server (bioid-mcp:<tag>)
#
# Build first (clean worktree of the commit), and smoke-test a backend image:
#   docker build -f Dockerfile.full -t cerit.io/tomsko/bat3-validation-api:<tag> .
#   deploy/smoke-worker.sh cerit.io/tomsko/bat3-validation-api:<tag>
#   docker push ...; digest: docker manifest inspect -v <image> (Descriptor.digest)
#
# Before changing anything it snapshots every touched deployment to
# $BIOID_SNAPSHOTS (default ~/bioid-release-snapshots; NOT in the repo: the
# specs carry environment values). Roll back with
#   kubectl -n ceitec-biodata-ns apply -f <snapshot>.yaml
# (`rollout undo` steps back only one of the two revisions a backend release makes.)
set -euo pipefail
NS=ceitec-biodata-ns
REG=cerit.io/tomsko
SNAP=${BIOID_SNAPSHOTS:-$HOME/bioid-release-snapshots}
BACKEND= CODE= WEB= DOCS= MCP= ALLOW_REPO=
while [ $# -gt 0 ]; do
  case "$1" in
    --backend) BACKEND=$2; shift 2 ;;
    --code) CODE=$2; shift 2 ;;
    --allow-repository) ALLOW_REPO=1; shift ;;
    --web) WEB=$2; shift 2 ;;
    --docs) DOCS=$2; shift 2 ;;
    --mcp) MCP=$2; shift 2 ;;
    -h|--help) sed -n 2,27p "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$BACKEND$WEB$DOCS$MCP" ] || { echo "nothing to release (see --help)" >&2; exit 2; }
if [ -n "$BACKEND" ]; then
  [[ "$BACKEND" == sha256:* ]] || { echo "--backend takes a sha256 digest" >&2; exit 2; }
  [ -n "$CODE" ] || { echo "--backend needs --code <git short sha>" >&2; exit 2; }
fi

image_exists() {  # the registry sometimes answers non-JSON once: retry
  for _ in 1 2 3 4; do docker manifest inspect "$1" >/dev/null 2>&1 && return 0; sleep 5; done
  echo "REFUSE: image not found: $1" >&2; return 1
}

[ -z "$BACKEND" ] || image_exists "$REG/bat3-validation-api@$BACKEND"
[ -z "$WEB" ] || image_exists "$REG/bat3-frontend:$WEB"
[ -z "$DOCS" ] || image_exists "$REG/bat3-docs:$DOCS"
[ -z "$MCP" ] || image_exists "$REG/bioid-mcp:$MCP"

if [ -n "$BACKEND" ]; then
  for q in celery validation.ui.celery validation.repo.celery bughunt; do
    [ -z "$ALLOW_REPO" ] || [ "$q" != validation.repo.celery ] || continue
    n=$(kubectl -n $NS exec deploy/bat3-redis -- redis-cli llen $q)
    [ "$n" = "0" ] || { echo "REFUSE: queue $q holds $n"; exit 1; }
  done
  # ask a live fleet worker (a fixed pod name goes stale after any rollout)
  # (no `| awk ... exit`: it closes the pipe early and pipefail aborts on SIGPIPE)
  P=$(kubectl -n $NS get pods -l app=bat3-ceitec-bat3-worker --field-selector=status.phase=Running \
        -o jsonpath='{.items[0].metadata.name}')
  [ -n "$P" ] || { echo "REFUSE: no running fleet worker to ask for active runs"; exit 1; }
  act=$(kubectl -n $NS exec -c worker "$P" -- sh -c 'cd /app && timeout 90 celery -A src_new.celery_app inspect active -j 2>/dev/null' \
        | SKIP=${ALLOW_REPO:+validation.repo.celery} python3 -c 'import os,sys,json; t=sys.stdin.read(); d=json.loads(t[t.find("{"):])
skip = os.environ.get("SKIP") or None
print(sum(1 for v in d.values() for x in (v or []) if (x.get("delivery_info") or {}).get("routing_key") != skip))')
  [ "$act" = "0" ] || { echo "REFUSE: $act active runs${ALLOW_REPO:+ outside the repository queue}"; exit 1; }
fi

mkdir -p "$SNAP"; chmod 700 "$SNAP"
stamp=$(date +%Y%m%d-%H%M%S)
touched=()
[ -z "$BACKEND" ] || touched+=(bat3-ceitec-bat3-api bat3-ceitec-bat3-worker bat3-ui-worker)
# the repository pool once it exists (deploy/bat3-repo-worker.yaml)
if [ -n "$BACKEND" ] && kubectl -n $NS get deploy bat3-repo-worker >/dev/null 2>&1; then
  touched+=(bat3-repo-worker); REPO=1
else REPO=; fi
[ -z "$WEB" ] || touched+=(bat3-ceitec-bat3-web)
[ -z "$DOCS" ] || touched+=(validation-docs)
[ -z "$MCP" ] || touched+=(bioid-mcp)
for d in "${touched[@]}"; do
  kubectl -n $NS get deploy "$d" -o yaml > "$SNAP/$d.pre-$stamp.yaml"
done
echo "snapshots: $SNAP/*.pre-$stamp.yaml"

if [ -n "$BACKEND" ]; then
  IMG=$REG/bat3-validation-api@$BACKEND
  kubectl -n $NS set image deploy/bat3-ceitec-bat3-worker worker=$IMG cache-seed=$IMG
  kubectl -n $NS set env deploy/bat3-ceitec-bat3-worker -c worker BAT3_CODE_VERSION=git-$CODE
  kubectl -n $NS set image deploy/bat3-ui-worker ui-worker=$IMG
  kubectl -n $NS set env deploy/bat3-ui-worker -c ui-worker BAT3_CODE_VERSION=git-$CODE
  if [ -n "$REPO" ]; then
    kubectl -n $NS set image deploy/bat3-repo-worker repo-worker=$IMG
    kubectl -n $NS set env deploy/bat3-repo-worker -c repo-worker BAT3_CODE_VERSION=git-$CODE
  fi
  kubectl -n $NS set image deploy/bat3-ceitec-bat3-api api=$IMG
  kubectl -n $NS set env deploy/bat3-ceitec-bat3-api -c api BAT3_CODE_VERSION=git-$CODE
fi
[ -z "$WEB" ] || kubectl -n $NS set image deploy/bat3-ceitec-bat3-web web=$REG/bat3-frontend:$WEB
[ -z "$DOCS" ] || kubectl -n $NS set image deploy/validation-docs docs=$REG/bat3-docs:$DOCS
[ -z "$MCP" ] || kubectl -n $NS set image deploy/bioid-mcp mcp=$REG/bioid-mcp:$MCP

for d in "${touched[@]}"; do
  kubectl -n $NS rollout status deploy/"$d" --timeout=40m | tail -1
done

if [ -n "$BACKEND" ]; then
  # Large fleets: re-limit RCSB load (validation fleet tooling, outside the repo).
  replicas=$(kubectl -n $NS get deploy bat3-ceitec-bat3-worker -o jsonpath='{.spec.replicas}')
  CONSUMERS=${BIOID_CONSUMERS_SH:-/home/tomsko/work/bat3_article_reviews/bioid_bughunt/rollout_b24/consumers.sh}
  if [ "$replicas" -gt 24 ]; then
    if [ -x "$CONSUMERS" ]; then "$CONSUMERS" 20 4 | tail -1
    else echo "WARNING: $replicas fleet workers; run consumers.sh 20 4 to re-limit RCSB load"; fi
  fi
fi

# Traps that bit before: secrets attached outside any manifest, the stale
# config overlay. Warn loudly; the release itself is done.
env_names() { kubectl -n $NS get deploy "$1" -o jsonpath='{range .spec.template.spec.containers[0].env[*]}{.name}{"\n"}{end}'; }
check_env() {  # deployment, names...
  local d=$1; shift; local have; have=$(env_names "$d")
  for n in "$@"; do grep -qx "$n" <<<"$have" || echo "WARNING: $d has no $n"; done
}
if [ -n "$BACKEND" ]; then
  check_env bat3-ceitec-bat3-api BAT3_IP_HASH_KEY BAT3_ADMIN_PASSWORD BAT3_RETENTION_ENFORCE BAT3_ALERT_EMAIL \
            BAT3_SHARED_CACHE_URL
  [ -z "$REPO" ] || check_env bat3-repo-worker NCBI_API_KEY BAT3_SHARED_CACHE_URL BAT3_RENDER_DISABLE
  check_env bat3-ui-worker NCBI_API_KEY BAT3_SHARED_CACHE_URL
  check_env bat3-ceitec-bat3-worker NCBI_API_KEY BAT3_SHARED_CACHE_URL
  for d in bat3-ui-worker bat3-ceitec-bat3-worker; do
    kubectl -n $NS get deploy $d -o jsonpath='{.spec.template.spec.volumes[*].name}' | grep -qw config-overlay \
      && echo "WARNING: $d still mounts the stale config overlay (bat3-config-overlay)"
  done
fi

for d in "${touched[@]}"; do
  echo "$d: $(kubectl -n $NS get pods -l app=$d -o jsonpath='{.items[0].status.containerStatuses[0].imageID}' 2>/dev/null)"
done
[ -z "$BACKEND" ] || { curl -s -m 30 https://bioid-ceitec.dyn.cloud.e-infra.cz/api/v1/capabilities | cut -c1-300; echo; }
