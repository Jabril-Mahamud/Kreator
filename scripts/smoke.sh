#!/usr/bin/env bash
# Heavy dogfooding smoke: generate a project, build its images, and verify at
# runtime the things that have silently broken before (see ISSUES.md). This needs
# Docker and a network, so it is NOT part of the default test suite; run it
# manually or on a nightly. Booting the full stack on Kind is still `kreator dev`.
set -euo pipefail

KREATOR="${KREATOR:-python -m kreator.main}"
WORKDIR="$(mktemp -d)"
IMAGE="kreator-smoke-frontend"
CID=""

cleanup() {
  [ -n "$CID" ] && docker rm -f "$CID" >/dev/null 2>&1 || true
  docker rmi -f "$IMAGE" >/dev/null 2>&1 || true
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

echo "==> generating demo project in $WORKDIR"
( cd "$WORKDIR" && $KREATOR init demo >/dev/null )
PROJECT="$WORKDIR/demo"

echo "==> building backend image (must build clean)"
docker build -q -t kreator-smoke-backend "$PROJECT/apps/backend" >/dev/null
docker rmi -f kreator-smoke-backend >/dev/null 2>&1 || true

echo "==> building frontend image"
docker build -q -t "$IMAGE" "$PROJECT/apps/frontend" >/dev/null

echo "==> booting frontend with a ported API URL"
PORTED_API="http://api.localhost:9100"
CID="$(docker run -d -e API_URL="$PORTED_API" "$IMAGE")"
sleep 4

# Issue #1: the entrypoint must rewrite the baked API URL in the static bundle.
# If the static dir is root-owned (the old bug), sed -i fails silently and the
# browser falls back to port 80. Assert the ported URL actually made it in.
echo "==> verifying API URL was rewritten in the static bundle"
if docker exec "$CID" sh -c "grep -rq 'api.localhost:9100' /home/appuser/.next/static"; then
  echo "PASS: frontend static bundle points at $PORTED_API"
else
  echo "FAIL: API URL was not rewritten; browser would call port 80 (ISSUES.md #1)" >&2
  exit 1
fi

echo "ALL SMOKE CHECKS PASSED"
