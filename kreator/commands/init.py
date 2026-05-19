from pathlib import Path

import typer

from kreator.core.config import KreatorConfig, save_config
from kreator.core.renderer import render_template_dir

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

PLATFORM_MAPPINGS = [
    ("platform/crossplane/xrds", "infrastructure/xrds"),
    ("platform/crossplane/compositions/local", "infrastructure/compositions/local"),
    ("platform/crossplane/compositions/civo", "infrastructure/compositions/civo"),
    ("platform/crossplane/provider-configs", "infrastructure/provider-configs"),
    ("platform/crossplane/claims", "infrastructure/claims"),
    ("platform/argocd", "deploy/argocd"),
    ("platform/helm/frontend", "deploy/helm/frontend"),
    ("platform/helm/backend", "deploy/helm/backend"),
    ("platform/observability", "deploy/observability"),
]


def init_command(
    name: str = typer.Argument(help="Project name (lowercase, alphanumeric, hyphens)"),
    frontend: str = typer.Option("nextjs", prompt="Frontend template", help="Frontend template"),
    backend: str = typer.Option("fastapi", prompt="Backend template", help="Backend template"),
    provider: str = typer.Option("civo", prompt="Cloud provider", help="Cloud provider"),
    region: str = typer.Option("lon1", prompt="Region", help="Provider region"),
) -> None:
    """Scaffold a new project."""
    try:
        config = KreatorConfig(
            name=name,
            frontend=frontend,
            backend=backend,
            provider=provider,
            region=region,
        )
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    project_dir = Path.cwd() / name

    if project_dir.exists():
        typer.echo(f"Error: directory '{name}' already exists", err=True)
        raise typer.Exit(1)

    project_dir.mkdir(parents=True)

    context = config.model_dump()

    project_templates = TEMPLATES_DIR / "project"
    if project_templates.exists():
        render_template_dir(project_templates, project_dir, context)

    backend_template = TEMPLATES_DIR / "backend" / config.backend
    if backend_template.exists():
        apps_dir = project_dir / "apps" / "backend"
        apps_dir.mkdir(parents=True, exist_ok=True)
        render_template_dir(backend_template, apps_dir, context)

    frontend_template = TEMPLATES_DIR / "frontend" / config.frontend
    if frontend_template.exists():
        apps_dir = project_dir / "apps" / "frontend"
        apps_dir.mkdir(parents=True, exist_ok=True)
        render_template_dir(frontend_template, apps_dir, context)

    for src_rel, dest_rel in PLATFORM_MAPPINGS:
        src = TEMPLATES_DIR / src_rel
        if src.exists():
            dest = project_dir / dest_rel
            dest.mkdir(parents=True, exist_ok=True)
            render_template_dir(src, dest, context)

    (project_dir / "secrets" / "raw").mkdir(parents=True, exist_ok=True)
    (project_dir / "secrets" / "sealed").mkdir(parents=True, exist_ok=True)

    save_config(config, project_dir / "kreator.yaml")

    typer.echo(f"Project '{name}' created at {project_dir}")
    typer.echo("Next steps:")
    typer.echo(f"  cd {name}")
    typer.echo("  kreator dev    # spin up local cluster")
