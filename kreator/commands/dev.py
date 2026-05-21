import logging
import sys
from pathlib import Path

import typer

from kreator.core.cluster import create_cluster, delete_cluster, wait_for_cluster_ready
from kreator.core.config import KreatorConfig, load_config
from kreator.core.platform import (
    apply_manifests,
    install_argocd,
    install_crossplane,
    install_helm_releases,
    install_ingress_nginx,
    install_sealed_secrets,
)
from kreator.core.registry import build_and_push, start_registry, stop_registry

logger = logging.getLogger(__name__)


def dev(
    destroy: bool = typer.Option(False, "--destroy", help="Tear down the local dev environment"),
    with_observability: bool = typer.Option(
        False, "--with-observability", help="Install the LGTM observability stack"
    ),
) -> None:
    """Spin up local Kind cluster with ArgoCD and Crossplane."""
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

    if destroy:
        _destroy()
        return

    _setup(project_dir, config, with_observability)


def _destroy() -> None:
    typer.echo("Tearing down local dev environment...")
    delete_cluster()
    stop_registry()
    typer.echo("Done. Cluster and registry removed.")


def _setup(project_dir: Path, config: KreatorConfig, with_observability: bool) -> None:
    typer.echo(f"Setting up local dev environment for '{config.name}'...")

    typer.echo("\n[1/6] Starting local registry...")
    start_registry()

    typer.echo("[2/6] Creating Kind cluster...")
    create_cluster()
    wait_for_cluster_ready()

    typer.echo("[3/6] Installing platform (Crossplane, ArgoCD, ingress, sealed-secrets)...")
    install_crossplane()
    install_ingress_nginx()
    install_sealed_secrets()
    install_argocd()

    typer.echo("[4/6] Building and pushing images...")
    build_and_push(f"{config.name}-backend", str(project_dir / "apps" / "backend"))
    build_and_push(f"{config.name}-frontend", str(project_dir / "apps" / "frontend"))

    typer.echo("[5/6] Applying infrastructure (XRDs, compositions, claims, secrets)...")
    apply_manifests(project_dir)

    typer.echo("[6/6] Installing application via Helm...")
    install_helm_releases(project_dir)

    if with_observability:
        typer.echo("Installing observability stack...")
        _install_observability()

    typer.echo("\nLocal dev environment ready!")
    typer.echo("  Frontend: http://frontend.localhost")
    typer.echo("  Backend:  http://api.localhost")
    typer.echo("\nTo tear down: kreator dev --destroy")


def _install_observability() -> None:
    from kreator.core.observability import install_observability_stack

    install_observability_stack()
