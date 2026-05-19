from pathlib import Path

import typer

from kreator.core.config import load_config
from kreator.providers.local import LocalProvider


def dev_command(
    destroy: bool = typer.Option(False, "--destroy", help="Tear down the local cluster"),
) -> None:
    """Spin up local Kind cluster and deploy via ArgoCD + Crossplane."""
    config_path = Path.cwd() / "kreator.yaml"
    if not config_path.exists():
        typer.echo(
            "Error: kreator.yaml not found. Run this from a kreator project directory.",
            err=True,
        )
        raise typer.Exit(1)

    config = load_config(config_path)
    project_dir = Path.cwd()
    provider = LocalProvider(config, project_dir)

    if destroy:
        typer.echo("Tearing down local environment...")
        provider.destroy()
        typer.echo("Local environment destroyed")
        return

    typer.echo(f"Setting up local dev environment for '{config.name}'...")
    provider.setup()

    typer.echo("")
    typer.echo("Local dev environment is ready!")
    typer.echo("Access your app at:")
    typer.echo("  Frontend: http://frontend.localhost")
    typer.echo("  Backend:  http://api.localhost")
    typer.echo("  ArgoCD:   kubectl port-forward svc/argocd-server -n argocd 8080:80")
    typer.echo("")
    typer.echo("To tear down: kreator dev --destroy")
