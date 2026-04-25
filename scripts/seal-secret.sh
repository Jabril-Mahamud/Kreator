#!/usr/bin/env bash
# Seal a Kubernetes Secret with kubeseal.
#
# Usage:
#   ./scripts/seal-secret.sh <secret-name> <namespace> <key=value> [<key=value>...]
#
# Example:
#   ./scripts/seal-secret.sh postgres-credentials default \
#     POSTGRES_USER=admin POSTGRES_PASSWORD=changeme POSTGRES_DB=app
#
# Writes:
#   secrets/raw/<secret-name>.yaml     (plain Secret, gitignored)
#   secrets/sealed/<secret-name>.yaml  (encrypted SealedSecret, safe to commit)

set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <secret-name> <namespace> <key=value> [<key=value>...]" >&2
  exit 1
fi

NAME="$1"
NAMESPACE="$2"
shift 2

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_DIR="$REPO_ROOT/secrets/raw"
SEALED_DIR="$REPO_ROOT/secrets/sealed"
mkdir -p "$RAW_DIR" "$SEALED_DIR"

for tool in kubectl kubeseal; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "error: '$tool' is required but not installed" >&2
    exit 1
  fi
done

LITERALS=()
for kv in "$@"; do
  if [[ "$kv" != *=* ]]; then
    echo "error: argument '$kv' is not key=value" >&2
    exit 1
  fi
  LITERALS+=(--from-literal="$kv")
done

RAW_FILE="$RAW_DIR/$NAME.yaml"
SEALED_FILE="$SEALED_DIR/$NAME.yaml"

kubectl create secret generic "$NAME" \
  --namespace "$NAMESPACE" \
  "${LITERALS[@]}" \
  --dry-run=client \
  -o yaml > "$RAW_FILE"

kubeseal \
  --controller-namespace kube-system \
  --controller-name sealed-secrets-controller \
  --format yaml \
  < "$RAW_FILE" \
  > "$SEALED_FILE"

echo "Wrote raw secret:    $RAW_FILE"
echo "Wrote sealed secret: $SEALED_FILE"
