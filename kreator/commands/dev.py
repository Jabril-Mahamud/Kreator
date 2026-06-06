import logging
import sys
from pathlib import Path

import typer

from kreator.core.cluster import create_cluster, delete_cluster, wait_for_cluster_ready
from kreator.core.config import KreatorConfig, load_config
from kreator.core.platform import (
    apply_manifests,
    check_prerequisites,
    deploy_git_server,
    get_argocd_password,
    install_argocd,
    install_crossplane,
    install_ingress_nginx,
    install_sealed_secrets,
    setup_argocd_apps,
    wait_for_argocd_sync,
    wait_for_db_ready,
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

    if destroy:
        _destroy()
        return

    project_dir = Path.cwd()
    config_path = project_dir / "kreator.yaml"

    if not config_path.exists():
        typer.echo(
            "Error: kreator.yaml not found. Run this from a kreator project directory.",
            err=True,
        )
        raise typer.Exit(1)

    config = load_config(config_path)
    _setup(project_dir, config, with_observability)


def _destroy() -> None:
    typer.echo("Tearing down local dev environment...")
    delete_cluster()
    stop_registry()
    typer.echo("Done. Cluster and registry removed.")


def _setup(project_dir: Path, config: KreatorConfig, with_observability: bool) -> None:
    typer.echo(f"Setting up local dev environment for '{config.name}'...")

    errors = check_prerequisites()
    if errors:
        typer.echo("Missing prerequisites:", err=True)
        for err in errors:
            typer.echo(f"  - {err}", err=True)
        raise typer.Exit(1)

    _ensure_git_committed(project_dir)

    typer.echo("\n[1/7] Starting local registry...")
    start_registry()

    typer.echo("[2/7] Creating Kind cluster...")
    create_cluster(project_dir)
    wait_for_cluster_ready()

    _preload_images()

    typer.echo("[3/7] Installing platform (Crossplane, ArgoCD, ingress, sealed-secrets)...")
    install_crossplane()
    install_ingress_nginx()
    install_sealed_secrets()
    install_argocd()

    typer.echo("[4/7] Building and pushing images...")
    build_and_push(f"{config.name}-backend", str(project_dir / "apps" / "backend"))
    for fe in config.web_frontends:
        build_and_push(f"{config.name}-{fe.name}", str(project_dir / "apps" / fe.name))

    typer.echo("[5/7] Applying infrastructure (XRDs, compositions, claims, secrets)...")
    apply_manifests(project_dir)
    wait_for_db_ready(config.name)

    typer.echo("[6/7] Deploying git server and configuring ArgoCD...")
    deploy_git_server()
    app_names = [f"{config.name}-backend"]
    for fe in config.web_frontends:
        app_names.append(f"{config.name}-{fe.name}")
    app_names.append(f"{config.name}-database")
    setup_argocd_apps(project_dir)

    typer.echo("[7/7] Waiting for ArgoCD to sync...")
    wait_for_argocd_sync(app_names, timeout=480)

    if with_observability:
        typer.echo("Installing observability stack...")
        _install_observability()

    password = get_argocd_password()
    typer.echo("\nLocal dev environment ready!")
    typer.echo(f"\n  ArgoCD:   http://localhost:9080/argocd  (admin / {password})")
    for fe in config.web_frontends:
        typer.echo(f"  {fe.name}: http://{fe.name}.localhost:9080")
    typer.echo("  Backend:  http://api.localhost:9080")

    for fe in config.mobile_frontends:
        typer.echo(
            f"\n  Mobile app '{fe.name}' is not deployed locally."
            f"\n  Run: cd apps/{fe.name} && npx expo start"
        )

    typer.echo("\nTo tear down: kreator dev --destroy")


def _ensure_git_committed(project_dir: Path) -> None:
    """Make sure the project has at least one commit so the git server can clone it."""
    from kreator.core.shell import run

    result = run(
        ["git", "-C", str(project_dir), "rev-parse", "HEAD"],
        capture=True, check=False,
    )
    if result.returncode == 0:
        return
    logger.info("creating initial git commit")
    run(["git", "-C", str(project_dir), "add", "-A"])
    run(["git", "-C", str(project_dir), "commit", "-m", "initial scaffold"])


def _preload_images() -> None:
    """Push common images to the local registry so kind nodes can pull them."""
    from kreator.core.registry import REGISTRY_PORT
    from kreator.core.shell import run

    images = ["postgres:16-alpine"]
    for image in images:
        result = run(
            ["docker", "image", "inspect", image],
            capture=True, check=False,
        )
        if result.returncode != 0:
            logger.info("pulling %s", image)
            run(["docker", "pull", image])
        local_tag = f"localhost:{REGISTRY_PORT}/{image}"
        logger.info("pushing %s to local registry", image)
        run(["docker", "tag", image, local_tag])
        run(["docker", "push", local_tag])


def _install_observability() -> None:
    from kreator.core.observability import install_observability_stack

    install_observability_stack()
