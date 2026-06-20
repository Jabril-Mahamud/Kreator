# Kreator

CLI tool that scaffolds deployment-ready full-stack applications with Kubernetes, Crossplane, and ArgoCD baked in.

Think `npm create next-app` but the output includes infrastructure-as-code, GitOps config, Helm charts, and observability, all wired together and ready to deploy.

## Install

```bash
pip install -e ".[dev]"
```

Requires Python 3.12+.

## Usage

```bash
kreator init my-app
cd my-app
kreator dev                  # Local Kind cluster with ArgoCD + Crossplane
kreator dev --refresh        # Rebuild images and redeploy to a running cluster
kreator dev --destroy        # Tear down the local dev environment
kreator doctor               # Check prerequisites and cluster health
kreator deploy               # Provision real infrastructure on Civo
kreator destroy              # Tear down cloud resources
```

## Available templates

| Layer    | Options                          | Platform |
|----------|----------------------------------|----------|
| Frontend | `nextjs`, `react` (Vite)         | web      |
| Frontend | `expo` (React Native)            | mobile   |
| Backend  | `fastapi`, `express`, `go`       |          |

Pick your stack at init time:

```bash
kreator init my-app --frontend react --backend express
```

## Multiple frontends

A single backend can serve multiple frontends. Use `name:template` syntax with repeatable `--frontend` flags:

```bash
kreator init my-app --frontend web:nextjs --frontend mobile:expo
```

This generates:
- `apps/web/` with a Next.js app, deployed to K8s via Helm and ArgoCD
- `apps/mobile/` with an Expo app, built via GitHub Actions and EAS Build
- `apps/backend/` shared by both

Web frontends get Helm charts, ArgoCD apps, and ingress rules. Mobile frontends get GitHub Actions CI workflows for building and publishing to app stores. Both share the same backend API.

If you only pass a template name without a prefix (e.g. `--frontend nextjs`), it behaves like before, creating a single frontend named `frontend`.

## What gets generated

A self-contained project with:

- Application code (frontend + backend + Dockerfiles)
- Crossplane XRDs and Compositions (local Kind and Civo)
- ArgoCD App-of-Apps config
- Helm charts for web frontends and backend
- Sealed Secrets
- LGTM observability stack (opt-in)
- GitHub Actions CI for mobile frontends (when applicable)

The generated project does not depend on the Kreator CLI to run after scaffolding. `kreator dev` and `kreator deploy` are convenience wrappers around kubectl, helm, and kind.

## Local development

`kreator dev` stands up a Kind cluster with:

- Crossplane (provider-kubernetes) provisioning a local Postgres
- ArgoCD syncing your app from an in-cluster git server
- nginx ingress routing to frontend and backend
- Images built and pushed to a local registry

Each project gets its own Kind cluster with its own host port, so the port is not fixed. `kreator dev` prints the assigned port when it finishes (you can also find it in `~/.kreator/clusters.json`). Substitute it for `<port>` below.

After making code changes, use `kreator dev --refresh` for a fast edit/redeploy loop. It rebuilds images, updates the in-cluster git server, and triggers an ArgoCD hard refresh without recreating the cluster or reinstalling platform components.

Access your web frontends at `http://<name>.localhost:<port>` (e.g. `http://frontend.localhost:<port>`) and the backend at `http://api.localhost:<port>`.

The ArgoCD dashboard is at `http://argocd.localhost:<port>`. Each project gets its own ArgoCD user, named after the project, that only sees that project's applications. Log in with `<project-name> / admin123` for the scoped view, or `admin / admin123` to see everything on the cluster. This matters when you run `kreator dev` from more than one project against the same Kind cluster; the project user keeps the dashboard clean.

Mobile frontends are not deployed to the local cluster. Run `cd apps/<name> && npx expo start` to start the Expo dev server.

Add `--with-observability` to install the LGTM stack (Loki, Grafana, Tempo, Mimir).

Tear down with `kreator dev --destroy`.

## Cloud deployment (Civo)

```bash
export CIVO_API_KEY=your-key-here
kreator deploy
```

This provisions a Civo Kubernetes cluster and managed database via Crossplane, installs ArgoCD on the cluster, and deploys your app. The cluster syncs from your git remote.

Get a Civo API key at https://dashboard.civo.com/security.

Tear down with `kreator destroy`.

## Development on Kreator itself

```bash
pip install -e ".[dev]"
pytest tests/                  # 92 unit tests
./scripts/smoke.sh             # Full init + Docker build smoke test
ruff check kreator/
ruff format kreator/
```

## Architecture

- **CLI**: Python, Typer, Jinja2 template rendering
- **Infrastructure**: Crossplane XRDs with environment-specific Compositions
- **Deployment**: ArgoCD App-of-Apps pattern
- **Local**: Kind cluster with local docker registry
- **Cloud**: Civo (AWS planned later)
