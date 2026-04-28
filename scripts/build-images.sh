#!/usr/bin/env bash
# Build and push app images to the local Kind registry.
#
# Usage:
#   ./scripts/build-images.sh                    # build every app in apps/ that has a Dockerfile
#   ./scripts/build-images.sh backend frontend   # build named apps only
#
# Each subdirectory of apps/ with a Dockerfile becomes an image named
# localhost:5001/kreator-<name>:latest

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY="localhost:5001"

if ! curl -fsS "http://${REGISTRY}/v2/" >/dev/null 2>&1; then
  echo "error: local registry is not reachable at http://${REGISTRY}" >&2
  echo "       run scripts/bootstrap.sh first to start the kind-registry container." >&2
  exit 1
fi

build_one() {
  local name="$1"
  local context="$REPO_ROOT/apps/$name"

  if [[ ! -f "$context/Dockerfile" ]]; then
    echo "error: no Dockerfile found at $context/Dockerfile" >&2
    exit 1
  fi

  local image="${REGISTRY}/kreator-${name}:latest"
  echo ">>> Building $image"
  docker build -t "$image" "$context"
  echo ">>> Pushing $image"
  docker push "$image"
}

# If no args, discover every apps/* subdirectory that has a Dockerfile
if [[ $# -eq 0 ]]; then
  targets=()
  for dir in "$REPO_ROOT/apps"/*/; do
    [[ -f "${dir}Dockerfile" ]] && targets+=("$(basename "$dir")")
  done
  if [[ ${#targets[@]} -eq 0 ]]; then
    echo "error: no apps with a Dockerfile found under apps/" >&2
    exit 1
  fi
else
  targets=("$@")
fi

for name in "${targets[@]}"; do
  build_one "$name"
done

echo ">>> Done. Catalog:"
curl -fsS "http://${REGISTRY}/v2/_catalog" || true
echo
