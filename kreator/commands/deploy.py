import logging
import sys
from pathlib import Path

import typer

from kreator.core.config import load_config
from kreator.core.platform import (
    install_argocd,
    install_crossplane,
    install_ingress_nginx,
    install_sealed_secrets,
    seal_secrets,
    setup_argocd_apps,
    wait_for_argocd_sync,
)
from kreator.providers.civo import (
    apply_civo_manifests,
    create_db_credentials_secret,
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

    repo_url = config.repo_url or ""
    if not repo_url or "OWNER" in repo_url:
        typer.echo(
            "Error: a real repo_url is required for cloud deploy. "
            "Set repo_url in kreator.yaml or pass it during kreator init.",
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
    from kreator.core.shell import run
    run(["kubectl", "create", "namespace", config.name], check=False)
    apply_civo_manifests(project_dir)

    typer.echo("[5/7] Waiting for infrastructure to provision...")
    wait_for_claims_ready(project_dir)

    typer.echo("[6/7] Creating secrets...")
    create_db_credentials_secret(config.name, namespace=config.name)
    seal_secrets(project_dir)

    typer.echo("[7/7] Configuring ArgoCD and waiting for sync...")
    setup_argocd_apps(project_dir, config.name)

    app_names = [f"{config.name}-backend"]
    for fe in config.web_frontends:
        app_names.append(f"{config.name}-{fe.name}")
    app_names.append(f"{config.name}-database")
    wait_for_argocd_sync(app_names, timeout=600)

    typer.echo("\nDeployment complete!")
    typer.echo(f"  Provider: {config.provider}")
    typer.echo(f"  Region:   {config.region}")
    typer.echo("\nTo tear down: kreator destroy")
