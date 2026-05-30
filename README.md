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
kreator deploy               # Provision real infrastructure on Civo
kreator destroy              # Tear down cloud resources
```

## Available templates

| Layer    | Options                     |
|----------|-----------------------------|
| Frontend | `nextjs`, `react` (Vite)    |
| Backend  | `fastapi`, `express`, `go`  |

Pick your stack at init time:

```bash
kreator init my-app --frontend react --backend express
```

## What gets generated

A self-contained project with:

- Application code (frontend + backend + Dockerfiles)
- Crossplane XRDs and Compositions (local Kind and Civo)
- ArgoCD App-of-Apps config
- Helm charts for both apps
- Sealed Secrets
- LGTM observability stack (opt-in)

The generated project does not depend on the Kreator CLI to run after scaffolding. `kreator dev` and `kreator deploy` are convenience wrappers around kubectl, helm, and kind.

## Local development

`kreator dev` stands up a Kind cluster with:

- Crossplane (provider-kubernetes) provisioning a local Postgres
- ArgoCD syncing your app from the local git repo
- nginx ingress routing to frontend and backend
- Images built and pushed to a local registry

Access your app at `http://frontend.localhost:9080` and `http://api.localhost:9080`.

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
pytest tests/
ruff check kreator/
ruff format kreator/
```

## Architecture

- **CLI**: Python, Typer, Jinja2 template rendering
- **Infrastructure**: Crossplane XRDs with environment-specific Compositions
- **Deployment**: ArgoCD App-of-Apps pattern
- **Local**: Kind cluster with local docker registry
- **Cloud**: Civo (AWS planned later)
