# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Non-negotiable rules

- Never mention "Claude", "Anthropic", or any AI tool in commit messages, code comments, PR descriptions, branch names, or any file in this repository. All work must appear as written by the repo owner.

## What this repo is

Kreator is a batteries-included local Kubernetes starter. `make up` provisions a Kind cluster running a Next.js frontend, FastAPI backend, Postgres, ArgoCD, Sealed Secrets, and the LGTM observability stack (Loki/Grafana/Tempo/Mimir). `make down` tears it all down.

## Common commands

### Cluster lifecycle
```bash
make up                          # Bootstrap entire stack (idempotent)
make down                        # Tear down cluster and registry
make rebuild                     # Rebuild Docker images and restart deployments
make status                      # Show ArgoCD application sync status
./scripts/bootstrap.sh --no-observability  # Skip LGTM stack (low-RAM machines)
```

### Backend (apps/backend)
```bash
cp apps/backend/.env.example apps/backend/.env   # once; edit if needed
pip install -e .
alembic upgrade head             # Run migrations
uvicorn app.main:app --reload    # Dev server on :8000
alembic revision --autogenerate -m "description"  # New migration
alembic downgrade base           # Roll back all migrations
```

### Frontend (apps/frontend)
```bash
cp apps/frontend/.env.local.example apps/frontend/.env.local   # once; edit if needed
npm install
npm run dev     # Dev server on :3000
npm run build   # Production build (required before Dockerfile builds)
```

### Images & secrets
```bash
make build                            # Build all apps in apps/ that have a Dockerfile
./scripts/build-images.sh backend     # Build a single named app
make seal-secret NAME=foo NS=default ARGS="KEY=val"  # Seal a secret
```

### Port-forwarding (alternative to *.localhost ingress)
```bash
make port-forward-argocd   # localhost:8080
make port-forward-grafana  # localhost:3000
```

## Architecture

### Deployment model
ArgoCD drives all in-cluster state via an App-of-Apps pattern. `platform/argocd/root-app.yaml` is the root Application; it watches `argocd-apps/` and reconciles the Application CRs there. Each Application CR points at either a chart in `charts/` (for the three app workloads) or an upstream Grafana Helm chart with values from `platform/observability/` (for LGTM components). **Local edits to charts or ArgoCD configs do not take effect until committed and pushed to the branch the Applications target.**

Sync waves enforce ordering: `postgres` (wave 0) → `backend` (wave 1) → `frontend` (wave 2). Observability components run at wave 0 in parallel.

### Sealed Secrets
Plain Kubernetes Secrets never enter git. The workflow is:
1. Write a plain Secret to `secrets/raw/<name>.yaml` (gitignored).
2. `seal-secret.sh` pipes it through `kubeseal`, writing a `SealedSecret` to `secrets/sealed/<name>.yaml`.
3. Only the committed sealed file is committed; only the in-cluster controller can decrypt it.

Sealed files are encrypted against the cluster's per-run keypair. After `make down` / `make up`, `bootstrap.sh` regenerates `postgres-credentials` and `backend-secrets` automatically.

### Backend (FastAPI)
- `app/config.py`: pydantic-settings reading `DATABASE_URL`, `APP_ENV`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `LOG_LEVEL`, `CORS_ORIGINS` from env.
- `app/database.py`: async SQLAlchemy 2.0 engine + session factory (asyncpg driver).
- `app/models.py` / `app/schemas.py`: `Item` (UUID pk, name, description, created_at).
- `app/routes/health.py`: `/healthz` (liveness) and `/readyz` (DB `SELECT 1`).
- `app/routes/items.py`: `GET/POST /api/items`, `GET/DELETE /api/items/{id}`.
- `app/telemetry.py`: wires OTLP tracing (gRPC), JSON structured logging with trace/span injection, and Prometheus metrics (`/metrics`). Falls back to `ConsoleSpanExporter` when `OTEL_EXPORTER_OTLP_ENDPOINT` is unset.
- Alembic migrations live in `alembic/versions/`; the backend Helm chart runs `alembic upgrade head` as an init container.

### Frontend (Next.js 14 App Router)
- Communicates with backend via `NEXT_PUBLIC_API_URL` (injected via Helm ConfigMap in-cluster, or env var locally).
- Built with `output: 'standalone'` in `next.config.js`; the Dockerfile copies `.next/standalone` into the runner stage.

### Helm charts (`charts/`)
Each of the three app charts (`backend`, `frontend`, `postgres`) follows the same structure: `Chart.yaml`, `values.yaml`, `templates/_helpers.tpl` (standard labels), and per-resource YAML. The backend chart includes an HPA and references the `backend-secrets` SealedSecret by name (not defining it). The postgres chart is a StatefulSet with `volumeClaimTemplates`.

### Adding a new app
1. Create `apps/<name>/Dockerfile` — `build-images.sh` auto-discovers it and builds `localhost:5001/kreator-<name>:latest`.
2. Add a Helm chart under `charts/<name>/` (copy `charts/frontend` or `charts/backend` as a starting point and adjust port/probes/values).
3. Add an ArgoCD Application CR in `argocd-apps/<name>.yaml` pointing at `charts/<name>`.

### Local registry
A `registry:2` container named `kind-registry` runs on `localhost:5001`. Kind nodes are patched to trust it via `containerdConfigPatches` in `kind-config.yaml`. Images are tagged `localhost:5001/kreator-<name>:latest`; app charts should set `imagePullPolicy: Always`.

### After forking
Replace `https://github.com/Jabril-Mahamud/Kreator.git` with your repo URL in:
- `platform/argocd/root-app.yaml`
- `argocd-apps/*.yaml`
