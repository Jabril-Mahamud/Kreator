# Kreator

A batteries-included local Kubernetes starter: a Kind cluster running a Next.js frontend and FastAPI backend backed by Postgres, deployed by ArgoCD, secured by Sealed Secrets, and observable through the LGTM stack (Loki, Grafana, Tempo, Mimir). One command up, one command down.

---

## Prerequisites

| Tool | Min version | macOS (brew) | Linux |
|------|-------------|--------------|-------|
| Docker | 24+ | `brew install --cask docker` | Distro package or [Docker Engine](https://docs.docker.com/engine/install/) |
| kind | 0.20+ | `brew install kind` | `go install sigs.k8s.io/kind@latest` or [release binary](https://kind.sigs.k8s.io/docs/user/quick-start/#installation) |
| kubectl | 1.28+ | `brew install kubectl` | `apt install kubectl` / `pacman -S kubectl` |
| Helm | 3.13+ | `brew install helm` | `apt install helm` / `pacman -S helm` |
| kubeseal | 0.24+ | `brew install kubeseal` | [release binary](https://github.com/bitnami-labs/sealed-secrets/releases) |

**Minimum system requirements:** 8 GB RAM allocated to Docker, 4 CPU cores. The observability stack (Loki/Grafana/Tempo/Mimir) is the heavy part — see [Troubleshooting](#troubleshooting) for the `--no-observability` flag.

---

## Quickstart

```bash
make up      # Bootstrap cluster, registry, platform, and apps
make down    # Tear everything down
```

After `make up`, these URLs become available:

| URL | Credentials |
|-----|-------------|
| http://frontend.localhost | — |
| http://api.localhost/docs | — |
| http://argocd.localhost | `admin` / `admin` |
| http://grafana.localhost | `admin` / `admin` |

`make help` lists every target.

---

## Repository layout

```
apps/
  frontend/                Next.js 14 app (App Router, TypeScript)
  backend/                 FastAPI app + SQLAlchemy + Alembic + OTel
charts/
  postgres/  backend/  frontend/    Custom Helm charts
platform/
  argocd/                  ArgoCD install values + root-app
  ingress/                 nginx-ingress install values
  sealed-secrets/          Sealed Secrets controller install values
  observability/           LGTM stack values + Grafana dashboard
argocd-apps/               ArgoCD Application CRs (App-of-Apps)
secrets/
  raw/                     Plain Secret YAML (gitignored)
  sealed/                  Encrypted SealedSecret YAML (committed)
scripts/
  bootstrap.sh  teardown.sh  build-images.sh  seal-secret.sh
kind-config.yaml           Kind cluster definition (1 cp + 2 workers)
Makefile
```

---

## Sealed Secrets workflow

Plain Kubernetes Secrets never enter git. Instead:

1. Write a plain Secret to `secrets/raw/<name>.yaml` (gitignored).
2. Encrypt it with the controller's public key using `kubeseal`, producing a `SealedSecret` in `secrets/sealed/<name>.yaml`.
3. Commit the sealed file. Only the in-cluster controller can decrypt it.

The helper script does all three:

```bash
make seal-secret NAME=my-app NS=default ARGS="API_KEY=abc DB_URL=postgres://..."
# or directly:
./scripts/seal-secret.sh my-app default API_KEY=abc DB_URL=postgres://...
```

`bootstrap.sh` regenerates `postgres-credentials` and `backend-secrets` on every `make up`. Sealed files are encrypted with the controller's per-cluster keypair, so a teardown invalidates whatever was sealed before — `secrets/sealed/` is therefore gitignored and rebuilt fresh each run.

---

## ArgoCD + repo workflow

`platform/argocd/root-app.yaml` defines a root Application that syncs everything in `argocd-apps/`. Each file there is an Application CR pointing at either a chart in this repo (`charts/{frontend,backend,postgres}`) or an upstream Grafana chart with values from `platform/observability/`.

After forking, point ArgoCD at your fork by replacing `https://github.com/Jabril-Mahamud/Kreator.git` with your repo URL in:
- `platform/argocd/root-app.yaml`
- `argocd-apps/*.yaml`

ArgoCD pulls the chart and Application sources from `main` of that URL — local edits to `charts/` or `argocd-apps/` won't take effect in the cluster until they're committed and pushed.

Sync waves: `postgres` (0) → `backend` (1) → `frontend` (2). Observability components sync in parallel at wave 0.

---

## Troubleshooting

**`*.localhost` doesn't resolve.** Most systems route `*.localhost` to `127.0.0.1` automatically. If yours doesn't, add to `/etc/hosts`:

```
127.0.0.1  frontend.localhost api.localhost argocd.localhost grafana.localhost
```

**Machine can't run the LGTM stack.** Skip it:

```bash
./scripts/bootstrap.sh --no-observability
```

The frontend, backend, and Postgres still come up — only Loki/Promtail/Tempo/Mimir/Grafana are skipped.

**Images aren't picked up after a code change.** Run `make rebuild` — it rebuilds, pushes to the local registry, and restarts the Deployments. Both app charts use `imagePullPolicy: Always`, so the rolled pod actually pulls the new `:latest`.

**ArgoCD Applications stay OutOfSync after editing a chart.** ArgoCD pulls from the git remote, not your working tree. Commit and push to `main` (or whichever branch the Applications target) before refreshing.

**`make up` finishes but `backend` and `postgres` are stuck in `CreateContainerConfigError` with `secret … not found`.** The committed sealed files were encrypted against a previous cluster's keypair. Delete `secrets/sealed/*.yaml` and re-run `make up` — bootstrap will reseal against the current controller. (This is now the default; old clones may still need the manual cleanup once.)

---

## Per-app development

- [`apps/frontend/README.md`](apps/frontend/README.md) — running the Next.js app locally without Kubernetes
- [`apps/backend/README.md`](apps/backend/README.md) — running the FastAPI app locally without Kubernetes
