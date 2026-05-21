from pathlib import Path

import typer

from kreator.core.config import KreatorConfig, discover_templates
from kreator.core.renderer import render_project


def init(
    name: str = typer.Argument(help="Project name"),
    frontend: str = typer.Option("nextjs", help="Frontend template"),
    backend: str = typer.Option("fastapi", help="Backend template"),
    provider: str = typer.Option("civo", help="Cloud provider (civo or local)"),
    region: str = typer.Option("lon1", help="Provider region"),
) -> None:
    """Scaffold a new project."""
    available_frontends = discover_templates("frontend")
    available_backends = discover_templates("backend")

    if frontend not in available_frontends:
        typer.echo(
            f"Error: frontend '{frontend}' not found. Available: {', '.join(available_frontends)}",
            err=True,
        )
        raise typer.Exit(1)

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

    config = KreatorConfig(
        name=name,
        frontend=frontend,
        backend=backend,
        provider=provider,
        region=region,
    )

    output_dir.mkdir(parents=True)
    files = render_project(config, output_dir)

    typer.echo(f"Created project '{name}' with {len(files)} files")
    typer.echo(f"  frontend: {frontend}")
    typer.echo(f"  backend:  {backend}")
    typer.echo(f"  provider: {provider}")
    typer.echo(f"  region:   {region}")
    typer.echo("\nNext steps:")
    typer.echo(f"  cd {name}")
    typer.echo("  kreator dev")
