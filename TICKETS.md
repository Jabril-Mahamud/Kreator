# Kreator — Implementation Tickets

Ordered work breakdown for building the Kreator Kubernetes starter template from `k8s-starter-spec.md`. Project is branded **Kreator**: the Kind cluster name is `kreator`, image prefix is `localhost:5001/kreator-*`, and README title uses "Kreator". Directory structure follows the spec verbatim.

Tickets are ordered by dependency. Each must pass its acceptance criteria before the next begins.

---

## K8S-001 — Repository scaffolding

**Description**
Create the top-level directory skeleton and baseline files:
- All directories from the spec: `apps/{frontend,backend}`, `charts/{frontend,backend,postgres}/templates`, `platform/{argocd,observability/dashboards,sealed-secrets,ingress}`, `argocd-apps`, `secrets/{sealed,raw}`, `config/base`, `scripts`.
- `.gitignore` exactly as specified (secrets/raw, kubeconfig, node_modules, .next, __pycache__, .venv, etc.).
- `secrets/raw/.gitkeep` placeholder.
- Replace the existing README.md stub with a short title-only placeholder (full README written in K8S-023).

**Acceptance criteria**
- `find . -type d` lists every directory in the spec's tree.
- `.gitignore` present with all required entries; `secrets/raw/` is ignored.
- `git status` is clean after an initial `git add .`.

**Dependencies:** none.

---

## K8S-002 — Backend FastAPI application (core)

**Description**
Implement the FastAPI app under `apps/backend/app/`:
- `main.py`: FastAPI instance, CORS middleware, routers, lifespan that calls telemetry setup.
- `config.py`: pydantic-settings class reading `DATABASE_URL`, `APP_ENV`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `LOG_LEVEL`.
- `database.py`: async SQLAlchemy 2.0 engine + `async_sessionmaker` using asyncpg.
- `models.py`: `Item(id: UUID, name: str, description: str, created_at: datetime)`.
- `schemas.py`: Pydantic `ItemCreate`, `ItemRead`.
- `routes/health.py`: `/healthz` (liveness), `/readyz` (DB `SELECT 1`).
- `routes/items.py`: `GET/POST /api/items`, `GET/DELETE /api/items/{id}`.
- `pyproject.toml` with FastAPI, uvicorn, SQLAlchemy[asyncio], asyncpg, pydantic-settings, alembic, and OTel + prometheus-client deps.

**Acceptance criteria**
- `uvicorn app.main:app` starts locally with a valid `DATABASE_URL` pointing at any Postgres.
- `curl /healthz` → `{"status":"ok"}`.
- `curl /readyz` returns 200 when DB reachable, 503 otherwise.
- CRUD endpoints work end-to-end against a Postgres instance.

**Dependencies:** K8S-001.

---

## K8S-003 — Backend observability instrumentation

**Description**
Implement `apps/backend/app/telemetry.py`:
- TracerProvider with OTLP gRPC/HTTP exporter to `OTEL_EXPORTER_OTLP_ENDPOINT`.
- FastAPI + SQLAlchemy auto-instrumentation.
- Structured JSON logger that injects `trace_id` and `span_id` into every log record.
- `/metrics` endpoint using `prometheus-client` (default process + HTTP request counters/histograms).
Wire `setup_telemetry(app)` into `main.py` startup.

**Acceptance criteria**
- Hitting any route produces a span visible via console exporter (used as fallback when OTLP endpoint unset).
- Logs are valid JSON lines containing `trace_id` and `span_id` when inside a request.
- `curl /metrics` returns Prometheus text format including `http_requests_total` or equivalent.

**Dependencies:** K8S-002.

---

## K8S-004 — Backend Alembic migrations

**Description**
Initialise Alembic under `apps/backend/alembic/`:
- `alembic.ini` reading `DATABASE_URL` from env.
- `env.py` configured for async engine, importing `models.Base.metadata`.
- One initial migration creating the `items` table (UUID pk, name text, description text, created_at timestamptz).

**Acceptance criteria**
- `alembic upgrade head` against an empty Postgres creates the `items` table.
- `alembic downgrade base` drops it cleanly.

**Dependencies:** K8S-002.

---

## K8S-005 — Frontend Next.js application

**Description**
Next.js 14 (App Router, TypeScript) under `apps/frontend/`:
- `package.json` (next, react, typescript).
- `next.config.js` with `output: 'standalone'`.
- `tsconfig.json`.
- `src/app/layout.tsx`, `src/app/page.tsx`: list items, form to create an item, health indicator based on `/healthz`, displays `HOSTNAME` env var.
- `src/lib/api.ts`: client using `process.env.NEXT_PUBLIC_API_URL`.

**Acceptance criteria**
- `npm install && npm run build` succeeds.
- `npm run start` serves the page; with a running backend at `NEXT_PUBLIC_API_URL`, items list and create form work.
- Health pill shows green when backend `/healthz` returns 200.

**Dependencies:** K8S-001 (backend not strictly required to build the UI).

---

## K8S-006 — Backend Dockerfile

**Description**
Multi-stage `apps/backend/Dockerfile`:
- `builder` stage: `python:3.12-slim`, install build deps, `pip install` into `/install`.
- `runner` stage: `python:3.12-slim`, copy installed site-packages and app code, create non-root user UID 1001, `USER 1001`, `EXPOSE 8000`, CMD `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- `.dockerignore` per spec.

**Acceptance criteria**
- `docker build -t kreator-backend apps/backend` succeeds.
- `docker run --rm kreator-backend id` shows UID 1001.
- Image runs and serves `/healthz` when `DATABASE_URL` is provided.

**Dependencies:** K8S-002, K8S-003, K8S-004.

---

## K8S-007 — Frontend Dockerfile

**Description**
Multi-stage `apps/frontend/Dockerfile`:
- `deps`: `node:20-alpine`, install prod deps.
- `builder`: copy source + deps, run `next build`.
- `runner`: `node:20-alpine`, copy `.next/standalone`, `.next/static`, `public`, create `nextjs` user UID 1001, `USER nextjs`, `EXPOSE 3000`, CMD `node server.js`.
- `.dockerignore` per spec.

**Acceptance criteria**
- `docker build -t kreator-frontend apps/frontend` succeeds.
- `docker run -p 3000:3000 kreator-frontend` serves the page on localhost:3000.
- Container process runs as non-root.

**Dependencies:** K8S-005.

---

## K8S-008 — PostgreSQL Helm chart

**Description**
`charts/postgres/` chart:
- `Chart.yaml`, `values.yaml` (image postgres:16-alpine, resources per spec, storage 1Gi).
- `templates/`: StatefulSet (single replica, volumeClaimTemplates, pg_isready probes, env from Secret `postgres-credentials`, non-root securityContext), headless Service, ConfigMap for postgres tuning, `_helpers.tpl` with standard labels, reference (not definition) of the `postgres-credentials` SealedSecret (actual SealedSecret lives in `secrets/sealed/`).

**Acceptance criteria**
- `helm lint charts/postgres` passes.
- `helm template charts/postgres` produces valid manifests with required labels `app.kubernetes.io/name`, `app.kubernetes.io/instance`.
- StatefulSet has `securityContext.runAsNonRoot: true` and a numeric `runAsUser`.

**Dependencies:** K8S-001.

---

## K8S-009 — Backend Helm chart

**Description**
`charts/backend/` chart:
- Deployment with liveness `/healthz`, readiness `/readyz`, resource requests/limits, env from ConfigMap + Secret (`backend-secrets`), Prometheus scrape annotations on pod template, security context non-root UID 1001 with readOnlyRootFilesystem where feasible.
- Init container running `alembic upgrade head` before the main container.
- Service (ClusterIP :8000), HPA (min 1 max 5, CPU 70%), ConfigMap with `APP_ENV`, `LOG_LEVEL`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `CORS_ORIGINS`.
- `_helpers.tpl` with standard labels. Image defaults to `localhost:5001/kreator-backend:latest`.

**Acceptance criteria**
- `helm lint charts/backend` passes.
- Rendered manifest contains the Alembic init container, HPA, prometheus scrape annotations, and references `backend-secrets`.
- No plaintext credentials in values.yaml.

**Dependencies:** K8S-006, K8S-008.

---

## K8S-010 — Frontend Helm chart

**Description**
`charts/frontend/` chart:
- Deployment with liveness/readiness probes on `/`, non-root, resource requests/limits, `HOSTNAME` env from fieldRef, `NEXT_PUBLIC_API_URL` from ConfigMap.
- Service (ClusterIP :80 → 3000), Ingress (`frontend.localhost`), HPA (min 1 max 5, CPU 70%), ConfigMap, `_helpers.tpl`.
- Image defaults to `localhost:5001/kreator-frontend:latest`.

**Acceptance criteria**
- `helm lint charts/frontend` passes.
- Rendered Ingress has host `frontend.localhost`, backend service name matches chart naming.
- Deployment injects `HOSTNAME` via downward API.

**Dependencies:** K8S-007.

---

## K8S-011 — Kind cluster config + local registry pattern

**Description**
- `kind-config.yaml` with 1 control-plane + 2 workers, ingress-ready label, hostPort 80/443 mappings.
- `containerdConfigPatches` section wiring nodes to `localhost:5001` local registry (per Kind docs).
- Registry wiring logic lives in `scripts/bootstrap.sh` (written in K8S-020); this ticket only delivers the kind config and validates it manually.

**Acceptance criteria**
- `kind create cluster --config kind-config.yaml --name kreator` produces a 3-node cluster.
- `kubectl get nodes` shows one control-plane labelled `ingress-ready=true`.

**Dependencies:** K8S-001.

---

## K8S-012 — Nginx Ingress install values

**Description**
`platform/ingress/install-values.yaml`: Kind-compatible values for `ingress-nginx` chart — nodeSelector on `ingress-ready=true`, tolerations for control-plane, hostPort enabled on 80/443, service type ClusterIP (traffic arrives via hostPort). Bootstrap will `helm install` using this file (platform bootstrap, not ArgoCD-managed, to avoid chicken-and-egg).

**Acceptance criteria**
- Applied via `helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx -f platform/ingress/install-values.yaml` against the Kind cluster.
- `kubectl -n ingress-nginx get pods` shows the controller Running on the control-plane node.
- `curl -I http://localhost` returns a 404 from nginx (proving ingress is reachable).

**Dependencies:** K8S-011.

---

## K8S-013 — Sealed Secrets controller + seal-secret.sh

**Description**
- `platform/sealed-secrets/install-values.yaml`: minimal values for the `sealed-secrets` Helm chart (namespace `kube-system`, controller resource requests).
- `scripts/seal-secret.sh`: per spec — builds a plain Secret from `key=value` args, pipes through `kubeseal --format yaml`, writes encrypted output to `secrets/sealed/<name>.yaml` and raw copy to `secrets/raw/<name>.yaml`.

**Acceptance criteria**
- Controller installs cleanly; `kubectl get sealedsecrets` works.
- `./scripts/seal-secret.sh demo default FOO=bar` produces `secrets/sealed/demo.yaml` that applies successfully and yields a Secret `demo` with `FOO=bar`.
- `secrets/raw/demo.yaml` is created but gitignored.

**Dependencies:** K8S-001, K8S-011.

---

## K8S-014 — ArgoCD install values + ingress

**Description**
`platform/argocd/install-values.yaml`: Dex disabled, server `--insecure`, admin password defaults to bcrypt hash of `admin`, Ingress enabled for `argocd.localhost`. Bootstrap installs via the official argo-cd Helm chart.

**Acceptance criteria**
- `helm install argocd argo/argo-cd -n argocd -f platform/argocd/install-values.yaml` completes.
- `http://argocd.localhost` loads the UI; login with `admin` / `admin` succeeds.
- Server pod running with `--insecure`.

**Dependencies:** K8S-012.

---

## K8S-015 — Loki + Promtail values

**Description**
- `platform/observability/loki-values.yaml`: `deploymentMode: SingleBinary`, single replica, filesystem storage, minimal resources.
- `platform/observability/promtail-values.yaml`: DaemonSet scraping all pod logs, shipping to in-cluster Loki service.

**Acceptance criteria**
- `helm template` against both charts renders without errors.
- Loki values explicitly set single-binary mode.
- Promtail clients point at `http://loki.observability.svc.cluster.local:3100/loki/api/v1/push`.

**Dependencies:** K8S-001.

---

## K8S-016 — Tempo + Mimir values

**Description**
- `platform/observability/tempo-values.yaml`: single-replica/monolithic mode, OTLP gRPC + HTTP receivers enabled, filesystem storage.
- `platform/observability/mimir-values.yaml`: monolithic mode (`deploymentMode: monolithic` or equivalent via `mimir-distributed` chart), filesystem/object-emulation storage, minimal resources.

**Acceptance criteria**
- `helm template` renders without errors.
- Tempo exposes OTLP endpoint on `:4317` (gRPC) reachable from the backend.
- Mimir exposes a Prometheus remote-write and query endpoint.

**Dependencies:** K8S-001.

---

## K8S-017 — Grafana values + starter-app dashboard

**Description**
- `platform/observability/grafana-values.yaml`: admin/admin, Ingress `grafana.localhost`, pre-provisioned data sources for Loki, Tempo, Mimir (using in-cluster service DNS), dashboard sidecar scraping ConfigMaps with label `grafana_dashboard=1`, dashboard provider pointing at `/var/lib/grafana/dashboards/starter-app`.
- `platform/observability/dashboards/starter-app.json`: 4 panels — HTTP request rate by endpoint (Mimir), p50/p95/p99 duration (Mimir), recent backend logs (Loki), trace search (Tempo) with traceId→logs correlation.

**Acceptance criteria**
- `grafana-values.yaml` renders valid datasource YAML for all three sources.
- `starter-app.json` is valid JSON and imports into a running Grafana without errors.
- Dashboard includes at least the four required panels wired to the correct datasource UIDs.

**Dependencies:** K8S-015, K8S-016.

---

## K8S-018 — ArgoCD Application CRs + App-of-Apps

**Description**
- `platform/argocd/root-app.yaml`: Application pointing at path `argocd-apps/` in the local repo.
- `argocd-apps/{postgres,backend,frontend,loki,grafana,tempo,mimir,promtail}.yaml`: each an Application CR.
  - Sync waves: postgres wave 0, backend wave 1, frontend wave 2; observability all wave 0.
  - `syncPolicy.automated.prune=true, selfHeal=true`.
  - App repoURL is a placeholder (`https://github.com/USER/kreator.git`) — bootstrap rewrites it to the locally-mounted repo URL.
  - Application sources point at `charts/<name>` for apps, and at upstream Grafana chart repos with `valueFiles` referencing `platform/observability/*-values.yaml` for LGTM components.

**Acceptance criteria**
- `kubectl apply --dry-run=client -f argocd-apps/ -f platform/argocd/root-app.yaml` passes.
- Each observability Application references the correct upstream chart (`grafana/loki`, `grafana/grafana`, `grafana/tempo`, `grafana/mimir-distributed`, `grafana/promtail`).
- Wave annotations present on postgres/backend/frontend.

**Dependencies:** K8S-008, K8S-009, K8S-010, K8S-014, K8S-015, K8S-016, K8S-017.

---

## K8S-019 — build-images.sh

**Description**
`scripts/build-images.sh [frontend|backend|all]` — default `all`. Builds each image tagged as `localhost:5001/kreator-<name>:latest` and pushes to the local registry. Fails fast with a readable message if the registry container isn't running.

**Acceptance criteria**
- With the registry up, `./scripts/build-images.sh all` builds and pushes both images.
- `curl http://localhost:5001/v2/_catalog` lists `kreator-frontend` and `kreator-backend`.
- Passing an unknown target prints usage and exits non-zero.

**Dependencies:** K8S-006, K8S-007.

---

## K8S-020 — bootstrap.sh

**Description**
Implement `scripts/bootstrap.sh` per spec §Scripts, idempotent throughout:
1. Prereq checks (docker, kind, kubectl, helm, kubeseal).
2. Start `kind-registry` container on `localhost:5001` if absent.
3. `kind create cluster --config kind-config.yaml --name kreator` if cluster absent; connect registry to the `kind` network; apply the `local-registry-hosting` ConfigMap.
4. Install ingress-nginx from `platform/ingress/install-values.yaml`; wait for rollout.
5. Install sealed-secrets controller; wait for rollout.
6. Generate random postgres credentials → `secrets/raw/` → seal into `secrets/sealed/postgres-credentials.yaml` and `secrets/sealed/backend-secrets.yaml` (only if not already present).
7. `scripts/build-images.sh all`.
8. Install ArgoCD from `platform/argocd/install-values.yaml`; wait for rollout.
9. Configure ArgoCD to watch the local repo (add the host-mounted path or local gitea — simplest option, documented as an assumption).
10. `kubectl apply -f platform/argocd/root-app.yaml` and all sealed secrets.
11. Poll ArgoCD Applications until all Synced+Healthy or 5-min timeout.
12. Print access URLs.

Support a `--no-observability` flag that skips the LGTM Applications.

**Acceptance criteria**
- On a clean machine, `./scripts/bootstrap.sh` completes end-to-end and prints access URLs.
- Running it a second time is a no-op (no errors, no duplicate resources).
- All URLs listed in the spec's verification checklist respond.

**Dependencies:** K8S-011, K8S-012, K8S-013, K8S-014, K8S-018, K8S-019.

---

## K8S-021 — teardown.sh

**Description**
`scripts/teardown.sh` per spec: `kind delete cluster --name kreator` then `docker rm -f kind-registry`. Tolerate either resource being already absent.

**Acceptance criteria**
- After `bootstrap.sh`, running `teardown.sh` removes the cluster and registry container.
- Running it again exits 0 with no errors.
- `docker ps` shows neither the cluster nodes nor `kind-registry`.

**Dependencies:** K8S-020.

---

## K8S-022 — Makefile

**Description**
Top-level `Makefile` with the targets specified: `up`, `down`, `build`, `rebuild`, `logs-frontend`, `logs-backend`, `status`, `seal-secret`, `port-forward-argocd`, `port-forward-grafana`. Include `.PHONY` and self-documenting help comments.

**Acceptance criteria**
- `make help` (or `make` with no args) lists every target with its comment.
- `make up` → `make down` is a full cycle.
- `make seal-secret NAME=foo NS=default ARGS="KEY=VALUE"` invokes the script correctly.

**Dependencies:** K8S-020, K8S-021.

---

## K8S-023 — README and documentation

**Description**
Replace `README.md` with full documentation:
- Title "Kreator" and one-paragraph purpose.
- Prerequisites table (Docker, kind, kubectl, Helm, kubeseal) with macOS (brew) and Linux (apt/pacman) install commands.
- Minimum system requirements (8GB Docker RAM, 4 CPU).
- Quickstart: `make up` / `make down`, access URLs.
- Repository layout summary.
- Sealed Secrets workflow explainer (raw → seal → commit sealed).
- ArgoCD + local repo workflow.
- Troubleshooting section: `/etc/hosts` fallback for `*.localhost` if DNS doesn't resolve; `--no-observability` flag for small machines.
- Per-app READMEs in `apps/frontend/README.md` and `apps/backend/README.md` covering local dev without k8s.

**Acceptance criteria**
- Following the README from a clean checkout lands on a working cluster.
- All commands and URLs in the README match the implementation.
- Per-app READMEs document local run commands that actually work.

**Dependencies:** everything above.
