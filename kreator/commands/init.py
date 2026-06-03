import subprocess
from pathlib import Path
from typing import Optional

import typer

from kreator.core.config import FrontendSpec, KreatorConfig, discover_templates
from kreator.core.renderer import render_project


def _parse_frontend_args(frontend: list[str]) -> list[FrontendSpec]:
    """Parse --frontend arguments into FrontendSpec list.

    Accepts 'template' (name defaults to 'frontend') or 'name:template'.
    """
    specs: list[FrontendSpec] = []
    for entry in frontend:
        if ":" in entry:
            name, template = entry.split(":", 1)
            specs.append(FrontendSpec(name=name, template=template))
        else:
            if len(frontend) > 1:
                raise typer.BadParameter(
                    f"Multiple frontends require name:template format, got '{entry}'"
                )
            specs.append(FrontendSpec(name="frontend", template=entry))
    return specs


def init(
    name: str = typer.Argument(help="Project name"),
    frontend: Optional[list[str]] = typer.Option(
        None, "--frontend", "-f", help="Frontend spec: 'template' or 'name:template' (repeatable)"
    ),
    backend: str = typer.Option("fastapi", help="Backend template"),
    provider: str = typer.Option("civo", help="Cloud provider (civo or local)"),
    region: str = typer.Option("lon1", help="Provider region"),
    repo_url: str = typer.Option("", "--repo-url", help="Git repo URL for ArgoCD sync"),
) -> None:
    """Scaffold a new project."""
    available_backends = discover_templates("backend")

    if backend not in available_backends:
        typer.echo(
            f"Error: backend '{backend}' not found. Available: {', '.join(available_backends)}",
            err=True,
        )
        raise typer.Exit(1)

    output_dir = Path.cwd() / name

    if output_dir.exists():
        typer.echo(f"Error: directory '{name}' already exists", err=True)
        raise typer.Exit(1)

    config_kwargs: dict = {
        "name": name,
        "backend": backend,
        "provider": provider,
        "region": region,
        "repo_url": repo_url,
    }

    if frontend:
        try:
            specs = _parse_frontend_args(frontend)
        except (typer.BadParameter, ValueError) as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)
        config_kwargs["frontends"] = specs
        config_kwargs["frontend"] = None
    else:
        config_kwargs["frontend"] = "nextjs"

    try:
        config = KreatorConfig(**config_kwargs)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    output_dir.mkdir(parents=True)
    files = render_project(config, output_dir)

    _git_init(output_dir)

    typer.echo(f"Created project '{name}' with {len(files)} files")
    for fe in config.frontends or []:
        typer.echo(f"  frontend: {fe.name} ({fe.template}, {fe.platform})")
    typer.echo(f"  backend:  {backend}")
    typer.echo(f"  provider: {provider}")
    typer.echo(f"  region:   {region}")
    typer.echo("\nNext steps:")
    typer.echo(f"  cd {name}")
    typer.echo("  kreator dev")


def _git_init(project_dir: Path) -> None:
    try:
        subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "add", "."], cwd=project_dir, check=True, capture_output=True, text=True
        )
        subprocess.run(
            ["git", "commit", "-m", "initial commit"],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
