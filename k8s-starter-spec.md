# k8s-starter — Project Specification

## Purpose

A single GitHub repository that can be cloned and bootstrapped with one command to produce a fully working local Kubernetes cluster running a sample full-stack application with GitOps (ArgoCD) and observability (LGTM stack). The goal is a reusable starter template for new Kubernetes projects, eliminating repetitive setup work.

---

## High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  Kind Cluster (1 control-plane + 2 worker nodes)                  │
│                                                                    │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐   │
│  │   Frontend    │   │   Backend    │   │     PostgreSQL       │   │
│  │  (Next.js)    │──▶│  (FastAPI)   │──▶│   (StatefulSet)      │   │
│  │  Deployment   │   │  Deployment  │   │                      │   │
│  │  + HPA        │   │  + HPA       │   │                      │   │
│  └──────────────┘   └──────────────┘   └──────────────────────┘   │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Platform Services                                           │  │
│  │  ┌─────────┐ ┌──────────────────┐ ┌───────────────────────┐ │  │
│  │  │ ArgoCD  │ │  LGTM Stack      │ │  Sealed Secrets       │ │  │
│  │  │         │ │  Loki + Grafana  │ │  Controller           │ │  │
│  │  │         │ │  Tempo + Mimir   │ │                       │ │  │
│  │  └─────────┘ └──────────────────┘ └───────────────────────┘ │  │
│  │  ┌──────────────────┐                                        │  │
│  │  │ Nginx Ingress    │                                        │  │
│  │  │ Controller       │                                        │  │
│  │  └──────────────────┘                                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
         ▲                    ▲                    ▲
         │                    │                    │
    localhost:80         localhost:3100        localhost:443
    (frontend,           (ArgoCD UI)          (Grafana)
     API via ingress)
```

---

## Repository Structure

```
k8s-starter/
│
├── apps/
│   ├── frontend/                    # Next.js application
│   │   ├── src/
│   │   │   ├── app/
│   │   │   │   ├── layout.tsx
│   │   │   │   └── page.tsx         # Simple page that calls backend API
│   │   │   └── lib/
│   │   │       └── api.ts           # API client for backend
│   │   ├── Dockerfile               # Multi-stage build, standalone output
│   │   ├── .dockerignore
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── next.config.js           # Standalone output mode
│   │   └── README.md
│   │
│   └── backend/                     # FastAPI application
│       ├── app/
│       │   ├── __init__.py
│       │   ├── main.py              # FastAPI app, CORS, routes
│       │   ├── config.py            # Settings via pydantic-settings (reads env vars)
│       │   ├── database.py          # SQLAlchemy async engine + session
│       │   ├── models.py            # SQLAlchemy ORM models
│       │   ├── schemas.py           # Pydantic request/response schemas
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── health.py        # /healthz and /readyz endpoints
│       │   │   └── items.py         # Sample CRUD resource
│       │   └── telemetry.py         # OpenTelemetry instrumentation setup
│       ├── alembic/                 # Database migrations
│       │   ├── alembic.ini
│       │   └── versions/
│       ├── Dockerfile               # Multi-stage build, slim Python image
│       ├── .dockerignore
│       ├── pyproject.toml
│       └── README.md
│
├── charts/
│   ├── frontend/
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   │       ├── deployment.yaml
│   │       ├── service.yaml
│   │       ├── ingress.yaml
│   │       ├── hpa.yaml
│   │       ├── configmap.yaml
│   │       └── _helpers.tpl
│   │
│   ├── backend/
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   │       ├── deployment.yaml
│   │       ├── service.yaml
│   │       ├── hpa.yaml
│   │       ├── configmap.yaml
│   │       ├── sealed-secret.yaml   # Reference to SealedSecret for DB creds
│   │       └── _helpers.tpl
│   │
│   └── postgres/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── statefulset.yaml
│           ├── service.yaml         # Headless service for StatefulSet
│           ├── pvc.yaml
│           ├── configmap.yaml       # pg_hba.conf, postgresql.conf overrides
│           ├── sealed-secret.yaml   # DB credentials
│           └── _helpers.tpl
│
├── platform/
│   ├── argocd/
│   │   ├── install-values.yaml      # ArgoCD Helm chart override values
│   │   └── root-app.yaml            # App-of-Apps root Application CR
│   │
│   ├── observability/
│   │   ├── loki-values.yaml
│   │   ├── grafana-values.yaml      # Includes pre-built dashboard provisioning
│   │   ├── tempo-values.yaml
│   │   ├── mimir-values.yaml
│   │   ├── promtail-values.yaml     # Or Grafana Alloy values
│   │   └── dashboards/
│   │       └── starter-app.json     # Pre-built Grafana dashboard
│   │
│   ├── sealed-secrets/
│   │   └── install-values.yaml      # Sealed Secrets controller config
│   │
│   └── ingress/
│       └── install-values.yaml      # Nginx ingress controller for Kind
│
├── argocd-apps/                     # ArgoCD Application custom resources
│   ├── frontend.yaml
│   ├── backend.yaml
│   ├── postgres.yaml
│   ├── loki.yaml
│   ├── grafana.yaml
│   ├── tempo.yaml
│   ├── mimir.yaml
│   └── promtail.yaml
│
├── secrets/
│   ├── sealed/                      # Encrypted SealedSecret manifests (safe to commit)
│   │   ├── postgres-credentials.yaml
│   │   └── backend-secrets.yaml
│   └── raw/                         # .gitignored — plaintext secrets for sealing
│       └── .gitkeep
│
├── config/
│   └── base/                        # Base ConfigMap values
│       ├── frontend.env
│       └── backend.env
│
├── scripts/
│   ├── bootstrap.sh                 # Full setup: cluster + registry + platform + apps
│   ├── teardown.sh                  # Destroy everything cleanly
│   ├── build-images.sh              # Build and load images into Kind
│   └── seal-secret.sh               # Helper to encrypt a secret with kubeseal
│
├── kind-config.yaml                 # Kind cluster configuration
├── Makefile                         # Developer-facing commands
├── .gitignore
└── README.md
```

---

## Component Specifications

### 1. Kind Cluster — `kind-config.yaml`

Create a multi-node Kind cluster optimised for local development.

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
  - role: worker
  - role: worker
```

Additionally, the bootstrap script must set up a **local Docker registry** container connected to the Kind network so that locally built images are available to the cluster without pushing to a remote registry. Use the documented Kind local registry pattern (registry running on `localhost:5001`, connected via a `kind` Docker network).

### 2. Frontend — Next.js Application

**Location:** `apps/frontend/`

A minimal Next.js 14+ application (App Router, TypeScript) that demonstrates connectivity to the backend.

**Functionality:**
- A single page that fetches and displays a list of "items" from the backend API
- A simple form to create a new item (name + description)
- Shows a health indicator (green/red) based on the backend `/healthz` response
- Displays the pod hostname (via an env var injected by the Deployment) to demonstrate scaling

**Dockerfile — multi-stage build:**
- Stage 1 (`deps`): `node:20-alpine`, install dependencies only
- Stage 2 (`builder`): copy source, run `next build` with `output: 'standalone'` in next.config.js
- Stage 3 (`runner`): `node:20-alpine`, copy standalone output + static + public, run as non-root user (`nextjs` user, UID 1001), expose port 3000
- Include a `.dockerignore` that excludes `node_modules`, `.next`, `.git`, `*.md`

**Environment variables consumed (via ConfigMap):**
- `NEXT_PUBLIC_API_URL` — backend API base URL (e.g., `http://backend.default.svc.cluster.local:8000`)

**Helm chart must include:**
- Deployment with liveness probe (`/`), readiness probe (`/`), resource requests/limits
- Service (ClusterIP, port 80 → 3000)
- Ingress (hostname: `frontend.localhost`)
- HPA (min: 1, max: 5, target CPU: 70%)
- ConfigMap for non-sensitive env vars

### 3. Backend — FastAPI Application

**Location:** `apps/backend/`

A minimal FastAPI application that provides a REST API with database connectivity and observability instrumentation.

**Functionality:**
- `GET /healthz` — liveness check (returns 200)
- `GET /readyz` — readiness check (verifies DB connectivity)
- `GET /api/items` — list all items from PostgreSQL
- `POST /api/items` — create a new item (name: str, description: str)
- `GET /api/items/{id}` — get a single item
- `DELETE /api/items/{id}` — delete an item
- CORS middleware allowing the frontend origin

**Configuration via `pydantic-settings`:**
- `DATABASE_URL` — PostgreSQL connection string (from Secret)
- `APP_ENV` — environment name (from ConfigMap)
- `OTEL_EXPORTER_OTLP_ENDPOINT` — OpenTelemetry collector endpoint (from ConfigMap)
- `LOG_LEVEL` — defaults to `INFO` (from ConfigMap)

**Database:**
- SQLAlchemy 2.0 async with asyncpg driver
- Single model: `Item(id: UUID, name: str, description: str, created_at: datetime)`
- Alembic for migrations with an initial migration that creates the items table

**Observability instrumentation (see Section 7):**
- OpenTelemetry SDK for tracing (push to Tempo via OTLP)
- Structured JSON logging (picked up by Promtail/Alloy → Loki)
- Prometheus metrics endpoint at `/metrics` (scraped by Mimir)

**Dockerfile — multi-stage build:**
- Stage 1 (`builder`): `python:3.12-slim`, install build dependencies, install Python deps via pip
- Stage 2 (`runner`): `python:3.12-slim`, copy installed packages and app code, run as non-root user (UID 1001), expose port 8000, entrypoint: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- `.dockerignore` excluding `.git`, `__pycache__`, `*.pyc`, `.venv`, `*.md`

**Helm chart must include:**
- Deployment with liveness probe (`/healthz`), readiness probe (`/readyz`), resource requests/limits
- Init container that runs Alembic migrations before the main container starts
- Service (ClusterIP, port 8000)
- HPA (min: 1, max: 5, target CPU: 70%)
- ConfigMap for non-sensitive env vars
- Environment variables from the postgres SealedSecret for `DATABASE_URL`

### 4. PostgreSQL

**Location:** `charts/postgres/`

A simple, custom Helm chart (not Bitnami) providing a single-instance PostgreSQL deployment suitable for local development.

**Resources to template:**
- **StatefulSet**: single replica, `postgres:16-alpine` image, port 5432
  - Volume mount for data at `/var/lib/postgresql/data`
  - Liveness probe: `pg_isready -U $POSTGRES_USER`
  - Readiness probe: same as liveness
  - Resource requests: 256Mi memory, 250m CPU
  - Environment variables from Secret: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- **Headless Service**: `clusterIP: None`, port 5432, for stable DNS (`postgres-0.postgres.default.svc.cluster.local`)
- **PersistentVolumeClaim**: 1Gi, `ReadWriteOnce` (Kind provides a default StorageClass)
- **ConfigMap**: optional PostgreSQL config overrides (shared_buffers, max_connections for local dev)
- **SealedSecret**: encrypted credentials for the database user and password

**Default values.yaml:**
```yaml
image:
  repository: postgres
  tag: "16-alpine"
replicaCount: 1
storage:
  size: 1Gi
resources:
  requests:
    memory: 256Mi
    cpu: 250m
  limits:
    memory: 512Mi
    cpu: 500m
```

### 5. Sealed Secrets — Config and Secret Management

**How configuration works in this project:**

There are two types of configuration an application needs:

1. **Non-sensitive config (ConfigMaps):** things like port numbers, log levels, environment names, API URLs. These are safe to store as plain text in the repo. Each Helm chart creates a ConfigMap from its `values.yaml`, and the Deployment mounts these as environment variables in the pod.

2. **Sensitive config (Secrets):** things like database passwords, API keys, tokens. These must not be stored as plain text in git.

**How Sealed Secrets works:**

Sealed Secrets is a Kubernetes controller that solves the "secrets in git" problem:

- A controller runs in the cluster and holds an encryption key pair
- You write a regular Kubernetes Secret in plain text locally (in the `secrets/raw/` directory, which is gitignored)
- You run `kubeseal` (a CLI tool) which encrypts the Secret using the controller's public key, producing a `SealedSecret` resource
- The encrypted `SealedSecret` is safe to commit to git (stored in `secrets/sealed/`)
- When ArgoCD deploys the `SealedSecret` to the cluster, the controller decrypts it and creates a regular Kubernetes Secret
- Pods then consume the Secret as normal environment variables or volume mounts

**Implementation:**

- Install the Sealed Secrets controller into the cluster during bootstrap (via Helm chart from `sealed-secrets` repo)
- Provide a helper script `scripts/seal-secret.sh` that wraps the `kubeseal` CLI:
  ```bash
  # Usage: ./scripts/seal-secret.sh <secret-name> <namespace> <key=value> [<key=value>...]
  # Example: ./scripts/seal-secret.sh postgres-credentials default POSTGRES_USER=admin POSTGRES_PASSWORD=changeme
  # Output: writes encrypted SealedSecret to secrets/sealed/<secret-name>.yaml
  ```
- The `secrets/raw/` directory is in `.gitignore` — plain text secrets never leave the local machine
- The `secrets/sealed/` directory contains only encrypted files and IS committed to git
- Each Helm chart that needs secrets references the corresponding SealedSecret resource by name

**Default secrets to pre-generate during bootstrap:**
- `postgres-credentials`: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `backend-secrets`: `DATABASE_URL` (constructed from the postgres credentials)

### 6. ArgoCD — GitOps

**ArgoCD manages all deployments after initial bootstrap.** The human never runs `helm install` manually for application workloads — everything goes through git.

**Installation:**
- Install ArgoCD into the `argocd` namespace using the official Helm chart with override values in `platform/argocd/install-values.yaml`
- Disable Dex (not needed for local dev)
- Set the admin password to a known default (e.g., `admin` / `admin`) for local dev convenience
- Configure the ArgoCD server to run with `--insecure` flag (no TLS termination, handled by ingress)
- Create an Ingress for the ArgoCD UI at `argocd.localhost`

**App-of-Apps pattern:**
- `platform/argocd/root-app.yaml` defines a root ArgoCD Application that points to the `argocd-apps/` directory
- Each file in `argocd-apps/` is an ArgoCD Application CR that defines how to deploy one component
- ArgoCD watches these files and syncs each Application independently

**Example ArgoCD Application CR (`argocd-apps/backend.yaml`):**
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: backend
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/<user>/k8s-starter.git   # Placeholder — user replaces after fork
    targetRevision: main
    path: charts/backend
  destination:
    server: https://kubernetes.default.svc
    namespace: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

**For local development with ArgoCD,** the bootstrap script should configure ArgoCD to point at the local filesystem or local git repo instead of a remote GitHub URL, so changes are picked up immediately without pushing. This can be done by adding the local repo as an ArgoCD repository source.

**ArgoCD Application CRs to create in `argocd-apps/`:**
- `postgres.yaml` — must sync first (other apps depend on it)
- `backend.yaml` — depends on postgres
- `frontend.yaml` — depends on backend
- `loki.yaml`
- `grafana.yaml`
- `tempo.yaml`
- `mimir.yaml`
- `promtail.yaml`

Use ArgoCD sync waves (annotations) to control ordering: postgres (wave 0) → backend (wave 1) → frontend (wave 2). Observability stack can sync in parallel (wave 0).

### 7. Observability — LGTM Stack

Deploy each LGTM component separately using the official Grafana Helm charts. Each gets its own ArgoCD Application and values file.

**Components:**

| Component | Helm Chart | Purpose | Namespace |
|-----------|-----------|---------|-----------|
| Loki | `grafana/loki` | Log aggregation | `observability` |
| Grafana | `grafana/grafana` | Dashboards and visualisation | `observability` |
| Tempo | `grafana/tempo` | Distributed tracing | `observability` |
| Mimir | `grafana/mimir-distributed` | Metrics (long-term Prometheus storage) | `observability` |
| Promtail | `grafana/promtail` | Log collection from nodes | `observability` |

**For local dev, use single-replica / monolithic modes** where available to reduce resource usage. Specifically:
- Loki: `singleBinary` deployment mode
- Tempo: single-replica mode
- Mimir: monolithic mode
- Promtail: DaemonSet (one per node, this is always the case)

**Grafana configuration (`platform/observability/grafana-values.yaml`):**
- Pre-configure data sources for Loki, Tempo, and Mimir so they work out of the box
- Provision the dashboard from `platform/observability/dashboards/starter-app.json`
- Create an Ingress at `grafana.localhost`
- Default credentials: `admin` / `admin`

**Pre-built dashboard (`starter-app.json`):**
A Grafana dashboard that shows:
- Panel 1: HTTP request rate by endpoint (from Mimir/Prometheus metrics)
- Panel 2: HTTP request duration p50/p95/p99 (from Mimir/Prometheus metrics)
- Panel 3: Recent log entries from the backend (from Loki)
- Panel 4: Trace search (from Tempo, linked to logs)

**Application instrumentation (backend):**

The FastAPI backend should be instrumented with OpenTelemetry:

```
opentelemetry-api
opentelemetry-sdk
opentelemetry-instrumentation-fastapi
opentelemetry-instrumentation-sqlalchemy
opentelemetry-exporter-otlp
prometheus-client
```

In `app/telemetry.py`:
- Set up a TracerProvider that exports spans via OTLP to Tempo
- Set up FastAPI auto-instrumentation (traces every request automatically)
- Set up SQLAlchemy auto-instrumentation (traces every DB query)
- Configure structured JSON logging with trace ID and span ID injected into log lines (this allows Grafana to correlate logs with traces)
- Expose a `/metrics` endpoint using `prometheus-client` for Prometheus-format metrics

The Deployment should have Prometheus scrape annotations:
```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/metrics"
```

### 8. Ingress — Nginx Ingress Controller

Install the Nginx Ingress Controller using the Kind-specific manifest or Helm chart with Kind-compatible config. This is required because Kind needs specific nodePort and hostPort mappings to route traffic from the host machine into the cluster.

**Ingress routes:**
| Hostname | Backend Service | Port |
|----------|----------------|------|
| `frontend.localhost` | frontend | 80 |
| `api.localhost` | backend | 8000 |
| `argocd.localhost` | argocd-server | 80 |
| `grafana.localhost` | grafana | 80 |

All hostnames resolve to `127.0.0.1` automatically on most systems (`.localhost` TLD). If not, the README should document adding them to `/etc/hosts`.

---

## Scripts

### `scripts/bootstrap.sh`

The main setup script. Must be idempotent (safe to re-run). Sequence:

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Prerequisite checks
#    - Verify: docker, kind, kubectl, helm, kubeseal are installed
#    - Print versions and fail fast with helpful install instructions if missing

# 2. Create local Docker registry (if not already running)
#    - Run registry container on localhost:5001
#    - Connect it to the kind network

# 3. Create Kind cluster
#    - kind create cluster --config kind-config.yaml --name k8s-starter
#    - Connect registry to the cluster network
#    - Configure nodes to use the local registry

# 4. Install Nginx Ingress Controller
#    - Apply the Kind-specific nginx ingress manifest
#    - Wait for ingress controller to be ready

# 5. Install Sealed Secrets controller
#    - helm install sealed-secrets ...
#    - Wait for controller to be ready

# 6. Generate and seal default secrets
#    - Generate random passwords for postgres
#    - Create raw secrets in secrets/raw/ (gitignored)
#    - Seal them with kubeseal → secrets/sealed/

# 7. Build and load application images
#    - docker build apps/frontend -t localhost:5001/frontend:latest
#    - docker build apps/backend -t localhost:5001/backend:latest
#    - docker push to local registry

# 8. Install ArgoCD
#    - helm install argocd ...
#    - Wait for ArgoCD to be ready
#    - Configure ArgoCD to use local repo

# 9. Apply root App-of-Apps
#    - kubectl apply -f platform/argocd/root-app.yaml
#    - ArgoCD takes over from here — syncs all applications

# 10. Wait for all applications to be healthy
#     - Poll ArgoCD Application statuses until all are Synced+Healthy
#     - Timeout after 5 minutes with helpful error messages

# 11. Print access URLs
#     - Frontend:  http://frontend.localhost
#     - Backend:   http://api.localhost
#     - ArgoCD:    http://argocd.localhost (admin/admin)
#     - Grafana:   http://grafana.localhost (admin/admin)
```

### `scripts/teardown.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
kind delete cluster --name k8s-starter
docker rm -f kind-registry 2>/dev/null || true
echo "Cluster and registry removed."
```

### `scripts/build-images.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
# Build and push images to the local registry
# Usage: ./scripts/build-images.sh [frontend|backend|all]
# Defaults to "all"
```

### `scripts/seal-secret.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
# Usage: ./scripts/seal-secret.sh <secret-name> <namespace> <key=value> [<key=value>...]
# 1. Creates a regular K8s Secret YAML from the key=value pairs
# 2. Pipes it through kubeseal to encrypt
# 3. Writes the SealedSecret to secrets/sealed/<secret-name>.yaml
# 4. Writes the raw Secret to secrets/raw/<secret-name>.yaml (gitignored, for reference)
```

---

## Makefile

```makefile
.PHONY: up down build rebuild logs status seal-secret

up:                    ## Bootstrap the entire stack
	./scripts/bootstrap.sh

down:                  ## Tear down cluster and registry
	./scripts/teardown.sh

build:                 ## Build and push images to local registry
	./scripts/build-images.sh all

rebuild: build         ## Rebuild images and restart deployments
	kubectl rollout restart deployment/frontend deployment/backend

logs-frontend:         ## Tail frontend logs
	kubectl logs -l app=frontend -f

logs-backend:          ## Tail backend logs
	kubectl logs -l app=backend -f

status:                ## Show status of all ArgoCD applications
	kubectl get applications -n argocd

seal-secret:           ## Seal a secret. Usage: make seal-secret NAME=mySecret NS=default ARGS="KEY=VALUE"
	./scripts/seal-secret.sh $(NAME) $(NS) $(ARGS)

port-forward-argocd:   ## Port-forward ArgoCD UI to localhost:8080
	kubectl port-forward svc/argocd-server -n argocd 8080:80

port-forward-grafana:  ## Port-forward Grafana to localhost:3000
	kubectl port-forward svc/grafana -n observability 3000:80
```

---

## .gitignore

```
# Secrets — never commit raw secrets
secrets/raw/

# Kind cluster config (auto-generated)
kubeconfig

# Docker
.docker/

# Node
node_modules/
.next/

# Python
__pycache__/
*.pyc
.venv/
*.egg-info/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

---

## Prerequisites

The README should document these prerequisites with install instructions for macOS (brew) and Linux (apt/pacman):

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| Docker | 24+ | Container runtime, Kind runs on Docker |
| kind | 0.20+ | Local Kubernetes cluster |
| kubectl | 1.28+ | Kubernetes CLI |
| Helm | 3.13+ | Package manager for Kubernetes |
| kubeseal | 0.24+ | CLI for encrypting secrets |

---

## Bootstrap Verification Checklist

After `make up` completes, the following should all be true:

- [ ] `kubectl get nodes` shows 3 nodes (1 control-plane, 2 workers) in Ready state
- [ ] `kubectl get pods -A` shows all pods Running/Completed
- [ ] `http://frontend.localhost` loads the Next.js app and displays items from the backend
- [ ] `http://api.localhost/docs` loads the FastAPI Swagger UI
- [ ] `http://api.localhost/healthz` returns `{"status": "ok"}`
- [ ] `http://argocd.localhost` loads the ArgoCD UI, all Applications are Synced and Healthy
- [ ] `http://grafana.localhost` loads Grafana with pre-configured datasources and the starter-app dashboard
- [ ] Creating an item via the frontend is visible in the Grafana dashboard (log entry + trace + metric increment)
- [ ] `kubectl get hpa` shows HPAs for frontend and backend
- [ ] `kubectl get sealedsecrets` shows the encrypted secrets
- [ ] Running `make down` followed by `make up` produces a clean, working environment

---

## Notes for the Implementer

1. **Start with the skeleton.** Get the repo structure, Dockerfiles, and bootstrap script working end-to-end before polishing individual components. A working pipeline is more valuable than a perfect component.

2. **Test the full bootstrap flow frequently.** Run `make down && make up` after each major addition to catch integration issues early.

3. **Keep the sample apps minimal.** The apps exist to prove the wiring — not to be a real product. One CRUD resource is enough. The value is in the infrastructure.

4. **Helm charts should be production-shaped** even though this is a local dev tool. That means: resource requests/limits on every container, security contexts (non-root, read-only root filesystem where possible), pod disruption budgets where appropriate, and proper label conventions (`app.kubernetes.io/name`, `app.kubernetes.io/instance`, etc.).

5. **The observability stack will be resource-heavy.** Document the minimum system requirements in the README (suggest at least 8GB RAM allocated to Docker, 4 CPU cores). Include a flag or make target to bootstrap without observability for machines that can't handle it.

6. **Local ArgoCD with git.** For the local development workflow, ArgoCD should be configured to watch the local filesystem or a local git server rather than requiring a GitHub remote. The simplest approach is to run a lightweight git server in the cluster (like gitea) or mount the host repo directory into the ArgoCD repo server pod.

7. **All Helm chart values should have sensible defaults** that work for local development without any overrides. The `values.yaml` files should be the single source of truth for local dev configuration.