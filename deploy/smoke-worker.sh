#!/bin/sh
# Pre-release smoke test of a backend image: start a real Celery worker from
# it against a throwaway Redis and require "ready". Catches dependency drift
# that unit tests cannot (2026-11-10: kombu 5.7 vs redis-py 5.0 crash-looped
# every worker after a rebuild). Run before release.sh:
#   deploy/smoke-worker.sh cerit.io/tomsko/bat3-validation-api:<tag>
set -eu
IMAGE=$1
NET=bioid-smoke-$$
cleanup() { docker rm -f "$NET-redis" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$NET-redis" --network "$NET" redis:7-alpine >/dev/null
sleep 2
out=$(timeout 120 docker run --rm --network "$NET" \
  -e CELERY_BROKER_URL="redis://$NET-redis:6379/0" -e CELERY_RESULT_BACKEND="redis://$NET-redis:6379/0" \
  --entrypoint sh "$IMAGE" -c 'cd /app && timeout 60 celery -A src_new.celery_app worker --loglevel=info --pool=threads -c 1 -Q validation.ui.celery 2>&1' || true)
if echo "$out" | grep -q "ready\."; then
  echo "OK: worker ready ($IMAGE)"
else
  echo "FAIL: worker did not start ($IMAGE)"; echo "$out" | tail -20; exit 1
fi
