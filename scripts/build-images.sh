#!/usr/bin/env bash
# Build and push Kreator images to the local Kind registry.
#
# Usage: ./scripts/build-images.sh [frontend|backend|all]
# Defaults to "all".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY="localhost:5001"
TARGET="${1:-all}"

case "$TARGET" in
  frontend|backend|all) ;;
  *)
    echo "Usage: $0 [frontend|backend|all]" >&2
    exit 1
    ;;
esac

if ! curl -fsS "http://${REGISTRY}/v2/" >/dev/null 2>&1; then
  echo "error: local registry is not reachable at http://${REGISTRY}" >&2
  echo "       run scripts/bootstrap.sh first to start the kind-registry container." >&2
  exit 1
fi

build_one() {
  local name="$1"
  local context="$REPO_ROOT/apps/$name"
  local image="${REGISTRY}/kreator-${name}:latest"

  echo ">>> Building $image from $context"
  docker build -t "$image" "$context"

  echo ">>> Pushing $image"
  docker push "$image"
}

if [[ "$TARGET" == "all" || "$TARGET" == "backend" ]]; then
  build_one backend
fi

if [[ "$TARGET" == "all" || "$TARGET" == "frontend" ]]; then
  build_one frontend
fi

echo ">>> Done. Catalog:"
curl -fsS "http://${REGISTRY}/v2/_catalog" || true
echo
