#!/bin/sh
# foldseek CPU-feature wrapper (installed as /usr/local/bin/foldseek in
# Dockerfile.full). The static release ships per-ISA builds; pick the best
# one the node supports. If neither works (exotic CPU), exec the sse2 build
# anyway and let it fail with a clear signal - the foldseek resolver treats a
# non-functional binary as "unavailable" and degrades gracefully (never fails
# a run).
if grep -q avx2 /proc/cpuinfo 2>/dev/null; then
    exec /opt/foldseek/foldseek-avx2 "$@"
fi
exec /opt/foldseek/foldseek-sse2 "$@"
