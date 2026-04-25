#!/usr/bin/env bash
# Tear down the Kreator Kind cluster and local registry.
# Idempotent — safe to re-run.

set -euo pipefail

CLUSTER_NAME="kreator"
REGISTRY_NAME="kind-registry"

if kind get clusters 2>/dev/null | grep -qx "$CLUSTER_NAME"; then
  echo "Deleting Kind cluster '${CLUSTER_NAME}'..."
  kind delete cluster --name "$CLUSTER_NAME"
else
  echo "Kind cluster '${CLUSTER_NAME}' not present — skipping."
fi

if docker inspect "$REGISTRY_NAME" >/dev/null 2>&1; then
  echo "Removing registry container '${REGISTRY_NAME}'..."
  docker rm -f "$REGISTRY_NAME" >/dev/null
else
  echo "Registry container '${REGISTRY_NAME}' not present — skipping."
fi

echo "Cluster and registry removed."
