#!/usr/bin/env bash
# Bootstrap the Kreator local Kubernetes stack end-to-end.
# Idempotent — safe to re-run.
#
# Flags:
#   --no-observability   Skip Loki/Promtail/Tempo/Mimir/Grafana ArgoCD apps.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CLUSTER_NAME="kreator"
REGISTRY_NAME="kind-registry"
REGISTRY_PORT=5001
KIND_NETWORK="kind"

NO_OBSERVABILITY=0
for arg in "$@"; do
  case "$arg" in
    --no-observability) NO_OBSERVABILITY=1 ;;
    *) echo "unknown flag: $arg" >&2; exit 1 ;;
  esac
done

log()  { printf "\033[1;36m[bootstrap]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[bootstrap]\033[0m %s\n" "$*"; }
fail() { printf "\033[1;31m[bootstrap]\033[0m %s\n" "$*" >&2; exit 1; }

# 1. Prerequisite checks
log "Checking prerequisites..."
for tool in docker kind kubectl helm kubeseal; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    fail "missing required tool: $tool — see README for install instructions"
  fi
  echo "  - $tool: $("$tool" version --short 2>/dev/null | head -n1 || "$tool" --version 2>/dev/null | head -n1 || echo present)"
done

# 2. Local registry
if [ "$(docker inspect -f '{{.State.Running}}' "$REGISTRY_NAME" 2>/dev/null || true)" != "true" ]; then
  log "Starting local registry container ${REGISTRY_NAME} on :${REGISTRY_PORT}..."
  docker run -d --restart=always \
    -p "127.0.0.1:${REGISTRY_PORT}:5000" \
    --name "$REGISTRY_NAME" \
    registry:2 >/dev/null
else
  log "Registry ${REGISTRY_NAME} already running."
fi

# 3. Kind cluster
if ! kind get clusters | grep -qx "$CLUSTER_NAME"; then
  log "Creating Kind cluster '${CLUSTER_NAME}'..."
  kind create cluster --config kind-config.yaml --name "$CLUSTER_NAME"
else
  log "Kind cluster '${CLUSTER_NAME}' already exists."
  kind export kubeconfig --name "$CLUSTER_NAME" >/dev/null
fi

# Ensure kubectl context
kubectl cluster-info --context "kind-${CLUSTER_NAME}" >/dev/null

# Connect registry to kind network
if ! docker network inspect "$KIND_NETWORK" -f '{{range .Containers}}{{.Name}} {{end}}' | grep -qw "$REGISTRY_NAME"; then
  log "Connecting registry to '${KIND_NETWORK}' network..."
  docker network connect "$KIND_NETWORK" "$REGISTRY_NAME" 2>/dev/null || true
fi

# Configure each node to use the local registry
log "Configuring nodes to use the local registry..."
REGISTRY_DIR="/etc/containerd/certs.d/localhost:${REGISTRY_PORT}"
for node in $(kind get nodes --name "$CLUSTER_NAME"); do
  docker exec "$node" mkdir -p "$REGISTRY_DIR"
  cat <<EOF | docker exec -i "$node" tee "${REGISTRY_DIR}/hosts.toml" >/dev/null
[host."http://${REGISTRY_NAME}:5000"]
EOF
done

# Document the registry per Kind convention
kubectl apply -f - <<EOF >/dev/null
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REGISTRY_PORT}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

# 4. Ingress controller
log "Installing ingress-nginx..."
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx >/dev/null 2>&1 || true
helm repo update ingress-nginx >/dev/null
kubectl create namespace ingress-nginx --dry-run=client -o yaml | kubectl apply -f - >/dev/null
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx \
  -f platform/ingress/install-values.yaml \
  --wait --timeout 5m

# 5. Sealed Secrets
log "Installing sealed-secrets controller..."
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets >/dev/null 2>&1 || true
helm repo update sealed-secrets >/dev/null
helm upgrade --install sealed-secrets sealed-secrets/sealed-secrets \
  -n kube-system \
  -f platform/sealed-secrets/install-values.yaml \
  --wait --timeout 5m

# Wait for the controller to publish its public key before sealing
log "Waiting for sealed-secrets controller to be ready..."
kubectl -n kube-system rollout status deploy/sealed-secrets-controller --timeout=120s

# 6. Generate sealed secrets against the current controller's keypair.
# A fresh `make down && make up` produces a new keypair, so any previously
# committed sealed files are undecryptable. Always regenerate.
gen_pw() {
  # Subshell with pipefail off — `head -c 24` exits before `tr` finishes,
  # so `tr` receives SIGPIPE (exit 141). Without this, pipefail+errexit
  # aborts the whole bootstrap.
  ( set +o pipefail; LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | head -c 24 )
}

log "Generating and sealing default secrets..."
PG_USER="kreator"
PG_PASS="$(gen_pw)"
PG_DB="kreator"
./scripts/seal-secret.sh postgres-credentials default \
  POSTGRES_USER="$PG_USER" \
  POSTGRES_PASSWORD="$PG_PASS" \
  POSTGRES_DB="$PG_DB"
DB_URL="postgresql+asyncpg://${PG_USER}:${PG_PASS}@postgres-0.postgres.default.svc.cluster.local:5432/${PG_DB}"
./scripts/seal-secret.sh backend-secrets default \
  DATABASE_URL="$DB_URL"

# 7. Build and push images
log "Building application images..."
./scripts/build-images.sh all

# 8. ArgoCD
log "Installing ArgoCD..."
helm repo add argo https://argoproj.github.io/argo-helm >/dev/null 2>&1 || true
helm repo update argo >/dev/null
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f - >/dev/null
helm upgrade --install argocd argo/argo-cd \
  -n argocd \
  -f platform/argocd/install-values.yaml \
  --wait --timeout 10m

# 9. Apply sealed secrets and root app
log "Applying sealed secrets..."
if compgen -G "secrets/sealed/*.yaml" >/dev/null; then
  kubectl apply -f secrets/sealed/
fi

log "Applying ArgoCD root application and app definitions..."
# Rewrite the canonical repo URL to whatever remote this clone uses.
CANONICAL_REPO_URL="https://github.com/Jabril-Mahamud/Kreator.git"
REMOTE_REPO_URL=$(git remote get-url origin 2>/dev/null || true)
patch_repo_url() {
  if [ -n "$REMOTE_REPO_URL" ] && [ "$REMOTE_REPO_URL" != "$CANONICAL_REPO_URL" ]; then
    sed "s|${CANONICAL_REPO_URL}|${REMOTE_REPO_URL}|g"
  else
    cat
  fi
}

patch_repo_url < platform/argocd/root-app.yaml | kubectl apply -f -

APPS_TO_APPLY=(postgres.yaml backend.yaml frontend.yaml)
if [ "$NO_OBSERVABILITY" -eq 0 ]; then
  APPS_TO_APPLY+=(loki.yaml promtail.yaml tempo.yaml mimir.yaml grafana.yaml)
else
  warn "--no-observability: skipping LGTM applications."
fi
for f in "${APPS_TO_APPLY[@]}"; do
  patch_repo_url < "argocd-apps/$f" | kubectl apply -f -
done

# 10. Wait for sync
log "Waiting for ArgoCD applications to become Synced+Healthy (timeout 10m)..."
deadline=$(( $(date +%s) + 600 ))
while :; do
  not_ready=$(kubectl -n argocd get applications.argoproj.io \
    -o jsonpath='{range .items[*]}{.metadata.name}={.status.sync.status},{.status.health.status}{"\n"}{end}' \
    | grep -v '=Synced,Healthy' || true)
  if [ -z "$not_ready" ]; then
    log "All applications Synced+Healthy."
    break
  fi
  if [ "$(date +%s)" -gt "$deadline" ]; then
    warn "Timeout waiting for applications. Current state:"
    echo "$not_ready"
    break
  fi
  sleep 10
done

# 11. Print URLs
cat <<EOF

============================================================
Kreator is up.

  Frontend:  http://frontend.localhost
  Backend:   http://api.localhost
  ArgoCD:    http://argocd.localhost   (admin / admin)
  Grafana:   http://grafana.localhost  (admin / admin)

If *.localhost does not resolve, add to /etc/hosts:
  127.0.0.1  frontend.localhost api.localhost argocd.localhost grafana.localhost
============================================================
EOF
