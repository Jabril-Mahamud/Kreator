# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Non-negotiable rules

- Never mention "Claude", "Anthropic", or any AI tool in commit messages, code comments, PR descriptions, branch names, or any file in this repository. All work must appear as written by the repo owner.
- Never use em dashes in any text, docs, or comments. Use commas, semicolons, or separate sentences instead.
- Avoid AI-sounding phrasing. Tone should be conversational, direct, and specific with no corporate filler.
- Do not add features, dependencies, or abstractions beyond what the current phase requires. Each phase must be complete and working before moving on.

## What this repo is

Kreator is a CLI tool that scaffolds deployment-ready full-stack applications with Kubernetes, Crossplane, and ArgoCD baked in. Think `npm create next-app` but the output includes infrastructure-as-code, GitOps config, Helm charts, and observability, all wired together and ready to deploy.

The developer experience:
```bash
kreator init my-app          # Scaffold a project (interactive prompts or flags)
cd my-app
kreator dev                  # Spin up local Kind cluster, deploy via ArgoCD + Crossplane
kreator dev --refresh        # Rebuild images and redeploy to a running cluster (fast edit loop)
kreator dev --destroy        # Tear down the local dev environment
kreator doctor               # Check prerequisites and cluster health
kreator deploy               # Provision real infrastructure on Civo and deploy
kreator destroy              # Tear down cloud resources
```

Kreator is NOT a starter template repo you clone. It is a CLI tool that generates projects. The generated project is self-contained and does not depend on the Kreator CLI to run after scaffolding (though `kreator dev` and `kreator deploy` are convenience wrappers).

## Architecture decisions (locked in)

These decisions are final. Do not revisit or suggest alternatives.

1. **Crossplane is the infrastructure layer.** Not Terraform, not Pulumi. Crossplane XRDs define the API, Compositions implement it per environment. Same Claim provisions a local StatefulSet on Kind or a managed database on Civo.

2. **ArgoCD is the deployment mechanism.** App-of-Apps pattern. The developer pushes to git, ArgoCD syncs. No imperative `helm install` for application workloads.

3. **Very opinionated.** One ingress controller (nginx). One secrets solution (Sealed Secrets). One observability stack (LGTM). No config options for these, they just work.

4. **Local dev mirrors production.** `kreator dev` runs the same Crossplane + ArgoCD pipeline on Kind that `kreator deploy` runs on Civo. The only difference is which Crossplane Compositions are active.

5. **Interchangeable app stacks via templates.** Starting with Next.js (frontend) and FastAPI (backend). Templates are Jinja2-rendered. Adding a new stack means adding a new template directory, nothing else changes. Projects can have multiple frontends (e.g. web + mobile), each from a different template.

6. **Default cloud provider is Civo.** AWS support comes later. Do not build AWS support until Civo is fully working.

## Tech stack

- **CLI**: Python 3.12+, Typer for commands, Jinja2 for template rendering, PyYAML for config
- **Generated web frontend**: Next.js 14 (App Router, TypeScript, standalone output) or React/Vite
- **Generated mobile frontend**: Expo (React Native) with Expo Router, EAS Build
- **Generated backend**: FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic
- **Infrastructure**: Crossplane with Kubernetes provider (local) and Civo provider (production)
- **GitOps**: ArgoCD with App-of-Apps
- **Secrets**: Sealed Secrets (kubeseal)
- **Observability**: Loki, Grafana, Tempo, Mimir, Promtail (opt-in addon)
- **Ingress**: nginx ingress controller
- **Local cluster**: Kind (1 control-plane + 2 workers)
- **Package/build**: pyproject.toml with setuptools, entry point `kreator`

## Generated project structure

When a user runs `kreator init my-app`, the output looks like this (single frontend default):

```
my-app/
  kreator.yaml                  # Project config (name, stacks, provider, region)
  Makefile                      # Convenience targets wrapping kreator commands
  README.md                     # Generated docs for this specific project
  apps/
    frontend/                   # Next.js, React, or Expo app (from template)
      src/
      Dockerfile                # Only for web frontends (nextjs, react)
      package.json
      ...
    backend/                    # FastAPI, Express, or Go app (from template)
      ...
  infrastructure/
    xrds/                       # Crossplane XRD definitions
      database.yaml
    compositions/
      local/                    # Kind: postgres StatefulSet + Service + Secret
        database.yaml
      civo/                     # Civo: managed database resource
        database.yaml
    claims/                     # What the developer edits
      database.yaml             # "I need a postgres database"
    provider-configs/
      local.yaml                # Crossplane Kubernetes provider config
      civo.yaml                 # Crossplane Civo provider config
  deploy/
    argocd/
      root-app.yaml             # App-of-Apps root
      apps/                     # One Application CR per web frontend + backend
        frontend.yaml           # Only generated for web frontends
        backend.yaml
        database.yaml           # ArgoCD manages the Crossplane Claims too
    helm/
      frontend/                 # Helm chart only for web frontends
        Chart.yaml
        values.yaml
        templates/
      backend/                  # Helm chart for backend deployment
        Chart.yaml
        values.yaml
        templates/
    ingress/
      ingress-nginx-values.yaml
    observability/              # LGTM values files
      grafana-values.yaml
      loki-values.yaml
      tempo-values.yaml
      mimir-values.yaml
      promtail-values.yaml
      dashboards/
        app.json
  secrets/
    raw/                        # Gitignored plain secrets (.gitkeep)
    sealed/                     # Sealed Secrets YAML
      secrets.yaml
```

With multiple frontends (`--frontend web:nextjs --frontend mobile:expo`), the structure changes:

```
my-app/
  apps/
    web/                        # Next.js app (web platform, deployed to K8s)
    mobile/                     # Expo app (mobile platform, built via EAS)
    backend/                    # Shared backend
  deploy/
    helm/
      web/                      # Helm chart for web frontend only
      backend/
    argocd/
      apps/
        web.yaml                # ArgoCD app for web frontend only
        backend.yaml
  .github/
    workflows/
      mobile-mobile.yml         # GitHub Actions CI for EAS Build
```

Mobile frontends do not get Helm charts, ArgoCD apps, or ingress rules. They get GitHub Actions workflows for EAS Build instead.

## kreator.yaml spec

Single frontend (default):
```yaml
name: my-app
frontend: nextjs          # nextjs | react | expo
backend: fastapi          # fastapi | express | go
database: postgres        # Only postgres for now
provider: civo            # civo | local (local is implicit for kreator dev)
region: lon1              # Provider-specific
repo_url: ""              # Git repo URL for ArgoCD sync (defaults to github.com/OWNER/<name>)
```

Multiple frontends:
```yaml
name: my-app
frontends:
  - name: web             # Directory name under apps/, also used for helm/argocd
    template: nextjs      # Which template to render
  - name: mobile
    template: expo
backend: fastapi
database: postgres
provider: civo
region: lon1
repo_url: ""
```

The `frontend` (singular) and `frontends` (list) fields are mutually exclusive. If `frontend` is used, it creates a single frontend named "frontend". Platform type (web or mobile) is derived from the template: nextjs/react are web, expo is mobile.

## CLI repo structure

```
kreator/
  kreator/                      # Python package
    __init__.py
    main.py                     # Typer app, entry point
    commands/
      init.py                   # kreator init
      dev.py                    # kreator dev (setup, --refresh, --destroy, --with-observability)
      deploy.py                 # kreator deploy
      destroy.py                # kreator destroy
      doctor.py                 # kreator doctor (prerequisite + cluster health checks)
    core/
      config.py                 # Load/validate kreator.yaml
      renderer.py               # Jinja2 template rendering engine
      platform.py               # Install platform components into a cluster
      cluster.py                # Kind cluster lifecycle
      registry.py               # Local docker registry
      observability.py          # LGTM stack installer
    providers/
      civo.py                   # Civo Crossplane provider setup + resource management
  templates/
    frontend/
      nextjs/                   # Jinja2-templated Next.js app (web platform)
      react/                    # Jinja2-templated React/Vite app (web platform)
      expo/                     # Jinja2-templated Expo/React Native app (mobile platform)
    backend/
      fastapi/                  # Jinja2-templated FastAPI app
      express/                  # Jinja2-templated Express/TypeScript app
      go/                       # Jinja2-templated Go app
    platform/                   # Shared platform templates
      argocd/
      crossplane/
        xrds/
        compositions/
          local/
          civo/
        provider-configs/
        claims/
      helm/
        frontend/               # Rendered per web frontend (parameterized by frontend_name)
        backend/
      observability/
      ingress/
    ci/
      mobile/                   # GitHub Actions workflow for EAS Build (rendered per mobile frontend)
    project/                    # Top-level project files
      kreator.yaml.j2
      Makefile.j2
      README.md.j2
      .gitignore.j2
      secrets/                  # Raw secrets template (.gitkeep)
  tests/
    test_init.py
    test_renderer.py
    test_config.py
    test_cluster.py
    test_doctor.py
    test_dogfood.py
    test_platform.py
    test_prerequisites.py
  scripts/
    smoke.sh                    # Manual smoke test (init + Docker build)
  pyproject.toml
  README.md
  CLAUDE.md
  ISSUES.md                     # Dogfooding bug log (all fixed, guarded by tests)
  TODO.md                       # Current work items
```

## Crossplane patterns

### XRD naming
Use `kreator.dev` as the API group. Example:
- `XDatabase` with group `kreator.dev`, version `v1alpha1`
- Claim kind: `Database`

### Composition structure
Each composition is environment-specific:

**Local composition (Kind):**
- Provisions a postgres StatefulSet + headless Service + Secret inside the cluster
- Uses the Crossplane Kubernetes provider (`provider-kubernetes`)
- The Secret contains POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, DATABASE_URL

**Civo composition:**
- Provisions a Civo DatabaseCluster using `provider-civo`
- Creates a connection Secret with the same keys as the local composition

The Claim interface is identical. The developer never thinks about which composition runs.

### Provider configs
- Local: `provider-kubernetes` with in-cluster service account
- Civo: `provider-civo` with API key from a Secret (user provides via `kreator deploy --civo-api-key` or env var)

## Helm chart patterns

Generated Helm charts follow these conventions:
- `_helpers.tpl` with standard labels (`app.kubernetes.io/name`, `app.kubernetes.io/instance`, etc.)
- All containers run as non-root (UID 1001)
- Resource requests and limits on every container
- Liveness and readiness probes on every container
- `imagePullPolicy: Always` for local registry images
- Secrets referenced by name (from Sealed Secrets), never defined in the chart
- ConfigMap for non-sensitive env vars
- Prometheus scrape annotations on backend pods
- HPA (min 1, max 5, CPU 70%) on frontend and backend

## Build phases

### Phase 1: CLI skeleton + template engine
- [x] Python package with Typer CLI (`kreator init`, `kreator dev`, `kreator deploy` as stubs)
- [x] Jinja2 template renderer that walks a template directory and renders into an output directory
- [x] kreator.yaml config loader and validator (Pydantic model)
- [x] Next.js app template (functional app with API client, health indicator, item CRUD)
- [x] FastAPI app template (functional app with health, CRUD, telemetry, alembic)
- [x] Dockerfiles for both apps (multi-stage, non-root)
- [x] Generated .gitignore, README.md, Makefile
- [x] `kreator init my-app` produces a working project where `cd my-app/apps/backend && pip install -e . && uvicorn app.main:app` works
- [x] Unit tests for renderer and config loader
- [x] `pip install -e .` installs the `kreator` command

**Done when:** `kreator init my-app` generates a complete project, both apps run locally outside Kubernetes.

### Phase 2: Local dev with Kind + Crossplane + ArgoCD
- [x] Kind cluster lifecycle (create, delete, registry, node config)
- [x] Platform installer: Crossplane (with provider-kubernetes), ArgoCD, ingress-nginx, Sealed Secrets
- [x] Crossplane XRD for Database
- [x] Local Composition: postgres StatefulSet + Service + Secret via provider-kubernetes
- [x] Generated Helm charts for frontend and backend (from templates)
- [x] Generated ArgoCD Application CRs (App-of-Apps)
- [x] Sealed Secrets generation (postgres creds, backend DATABASE_URL)
- [x] Image build + push to local registry
- [x] ArgoCD pointed at local git repo
- [x] `kreator dev` runs the full pipeline: cluster up, platform installed, app deployed via ArgoCD, Crossplane provisions database
- [x] `kreator dev --destroy` tears it down
- [x] Access URLs: frontend.localhost, api.localhost, argocd.localhost

**Done when:** `kreator init my-app && cd my-app && kreator dev` produces a running app on Kind, deployed through ArgoCD, with database provisioned by Crossplane.

### Phase 3: Civo deployment
- [x] Civo Crossplane provider setup
- [x] Civo Composition: managed Kubernetes cluster + managed database
- [x] `kreator deploy` provisions infrastructure on Civo via Crossplane
- [x] ArgoCD installed on the Civo cluster, pointed at the git remote
- [x] `kreator destroy` tears down Civo resources
- [x] Docs for Civo API key setup

**Done when:** `kreator deploy` provisions a Civo cluster and database, deploys the app via ArgoCD.

### Phase 4: Observability + additional templates
- [x] LGTM stack as opt-in addon (`kreator dev --with-observability`)
- [x] Grafana dashboard template
- [x] Pre-configured datasources (Loki, Tempo, Mimir)
- [x] React/Vite frontend template
- [x] Express/TypeScript backend template
- [x] Go backend template
- [x] Verify interchangeability: `kreator init --frontend react --backend express` works end to end

**Done when:** Observability works as an addon, multiple stack combinations are supported.

### Phase 5: Multi-frontend + mobile support
- [x] `FrontendSpec` model with name, template, and platform (web/mobile)
- [x] Repeatable `--frontend` flag with `name:template` syntax
- [x] Renderer loops over frontends, generates per-frontend helm/argocd for web, CI for mobile
- [x] Expo (React Native) frontend template with Expo Router, SecureStore auth, todo CRUD
- [x] GitHub Actions CI template for EAS Build (mobile frontends)
- [x] Backwards compatibility: single `--frontend nextjs` and `frontend:` in kreator.yaml still work
- [x] Dynamic filename rendering in templates (Jinja2 expressions in filenames)
- [x] `install_helm_releases` dynamically discovers charts instead of hardcoding frontend/backend

**Done when:** `kreator init my-app --frontend web:nextjs --frontend mobile:expo` produces a working multi-frontend project.

## Common commands during development

```bash
# Install the CLI in dev mode
pip install -e ".[dev]"

# Run the CLI
kreator init my-app
kreator dev
kreator dev --refresh          # Fast edit/redeploy loop
kreator dev --destroy           # Tear down local cluster
kreator doctor                  # Check tool prerequisites and cluster health
kreator deploy
kreator destroy

# Run tests
pytest tests/

# Run smoke test (requires Docker, verifies full init+build pipeline)
./scripts/smoke.sh

# Lint
ruff check kreator/
ruff format kreator/
```

## Testing approach

- Unit tests for the template renderer, config loader, provider logic, cluster port allocation, and dogfood regression guards (92 tests, all passing)
- Integration test: `kreator init` generates a project, verify file structure and content
- Smoke test (`scripts/smoke.sh`): runs `kreator init` + Docker build to verify the full template pipeline produces buildable images. Requires Docker, runs manually.
- No need to spin up Kind in CI for now. Local manual testing of Phase 2+ is fine.

## Style and conventions

- Python: ruff for linting and formatting, type hints on all functions
- YAML: 2-space indent
- Helm: follow the label and naming conventions from the current Kreator charts
- Commits: imperative mood, lowercase, no period ("add fastapi template" not "Added FastAPI template.")
- Branch naming: `phase-1/cli-skeleton`, `phase-2/local-dev`, etc.