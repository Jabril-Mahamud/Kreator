import logging
import sys
from pathlib import Path

import typer

from kreator.core.config import load_config
from kreator.core.platform import (
    install_argocd,
    install_crossplane,
    install_helm_releases,
    install_ingress_nginx,
    install_sealed_secrets,
)
from kreator.providers.civo import (
    apply_civo_manifests,
    create_app_secrets,
    install_crossplane_provider_civo,
    setup_civo_api_key_secret,
    wait_for_claims_ready,
)


def deploy(
    civo_api_key: str = typer.Option(
        None, "--civo-api-key", envvar="CIVO_API_KEY", help="Civo API key"
    ),
) -> None:
    """Deploy to cloud infrastructure via Crossplane."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stdout,
    )

    project_dir = Path.cwd()
    config_path = project_dir / "kreator.yaml"

    if not config_path.exists():
        typer.echo(
            "Error: kreator.yaml not found. Run this from a kreator project directory.",
            err=True,
        )
        raise typer.Exit(1)

    config = load_config(config_path)

    if config.provider != "civo":
        typer.echo(
            f"Error: kreator deploy only supports civo provider, got '{config.provider}'",
            err=True,
        )
        raise typer.Exit(1)

    if not civo_api_key:
        typer.echo(
            "Error: Civo API key required. Pass --civo-api-key or set CIVO_API_KEY env var.",
            err=True,
        )
        raise typer.Exit(1)

    typer.echo(f"Deploying '{config.name}' to Civo ({config.region})...")

    typer.echo("\n[1/7] Installing Crossplane...")
    install_crossplane()

    typer.echo("[2/7] Setting up Civo provider...")
    setup_civo_api_key_secret(civo_api_key)
    install_crossplane_provider_civo()

    typer.echo("[3/7] Installing platform components...")
    install_ingress_nginx()
    install_sealed_secrets()
    install_argocd()

    typer.echo("[4/7] Applying Civo infrastructure...")
    apply_civo_manifests(project_dir)

    typer.echo("[5/7] Waiting for infrastructure to provision...")
    wait_for_claims_ready(project_dir)

    typer.echo("[6/7] Creating application secrets from database credentials...")
    create_app_secrets(config.name)

    typer.echo("[7/7] Installing application via Helm...")
    install_helm_releases(project_dir)

    typer.echo("\nDeployment complete!")
    typer.echo(f"  Provider: {config.provider}")
    typer.echo(f"  Region:   {config.region}")
    typer.echo("\nTo tear down: kreator destroy")
