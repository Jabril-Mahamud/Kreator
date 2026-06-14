import logging
import sys
from pathlib import Path

import typer

from kreator.core.cluster import (
    allocate_ports,
    cluster_name,
    create_cluster,
    delete_cluster,
    list_kreator_clusters,
    release_ports,
    wait_for_cluster_ready,
)
from kreator.core.config import KreatorConfig, load_config
from kreator.core.platform import (
    GIT_SERVER_URL,
    apply_manifests,
    check_prerequisites,
    deploy_git_server,
    get_argocd_password,
    install_argocd,
    install_crossplane,
    install_ingress_nginx,
    install_sealed_secrets,
    patch_argocd_repo_url,
    patch_claims_for_env,
    seal_secrets,
    setup_argocd_apps,
    wait_for_db_ready,
)
from kreator.core.registry import build_and_push, start_registry, stop_registry
from kreator.core.shell import run

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
        _destroy(config)
        return

    _setup(project_dir, config, with_observability)


def _destroy(config: KreatorConfig) -> None:
    typer.echo(f"Tearing down local dev environment for '{config.name}'...")
    name = cluster_name(config.name)
    delete_cluster(name)
    release_ports(name)
    # The local registry is shared across all project clusters; only stop it
    # once no kreator clusters remain.
    if not list_kreator_clusters():
        stop_registry()
        typer.echo("Done. Cluster and registry removed.")
    else:
        typer.echo(f"Done. Cluster '{name}' removed (shared registry left running).")


def _setup(project_dir: Path, config: KreatorConfig, with_observability: bool) -> None:
    typer.echo(f"Setting up local dev environment for '{config.name}'...")

    errors = check_prerequisites()
    if errors:
        typer.echo("Missing prerequisites:", err=True)
        for err in errors:
            typer.echo(f"  - {err}", err=True)
        raise typer.Exit(1)

    _prepare_for_local_dev(project_dir)
    _ensure_git_committed(project_dir)

    typer.echo("\n[1/6] Starting local registry...")
    start_registry()

    typer.echo("[2/6] Creating Kind cluster...")
    name = cluster_name(config.name)
    http_port, https_port = allocate_ports(name)
    create_cluster(name, http_port, https_port, project_dir)
    wait_for_cluster_ready()

    _preload_images()

    typer.echo("[3/6] Installing platform (Crossplane, ArgoCD, ingress, sealed-secrets)...")
    install_crossplane()
    install_ingress_nginx()
    install_sealed_secrets()
    install_argocd()

    typer.echo("[4/6] Building and pushing images, sealing secrets...")
    run(["kubectl", "create", "namespace", config.name], check=False)
    build_and_push(f"{config.name}-backend", str(project_dir / "apps" / "backend"))
    for fe in config.web_frontends:
        build_and_push(f"{config.name}-{fe.name}", str(project_dir / "apps" / fe.name))
    seal_secrets(project_dir)
    _ensure_git_committed(project_dir)

    typer.echo("[5/6] Applying infrastructure (XRDs, compositions, claims)...")
    apply_manifests(project_dir)
    wait_for_db_ready(config.name, namespace=config.name)

    typer.echo("[6/6] Deploying git server and configuring ArgoCD...")
    deploy_git_server()
    setup_argocd_apps(project_dir, config.name)

    if with_observability:
        typer.echo("Installing observability stack...")
        _install_observability()

    password = get_argocd_password()
    typer.echo("\nLocal dev environment ready!")
    typer.echo(f"\nCluster: {name} (http {http_port}, https {https_port})")
    typer.echo("\nArgoCD is syncing your apps. Watch progress in the dashboard:")
    typer.echo(f"\n  ArgoCD:   http://argocd.localhost:{http_port}  ({config.name} / {password})")
    typer.echo(f"            log in as '{config.name}' to see only this project's apps")
    typer.echo(f"            (admin / {password} shows everything)")
    for fe in config.web_frontends:
        typer.echo(f"  {fe.name}: http://{fe.name}.localhost:{http_port}")
    typer.echo(f"  Backend:  http://api.localhost:{http_port}")

    for fe in config.mobile_frontends:
        typer.echo(
            f"\n  Mobile app '{fe.name}' is not deployed locally."
            f"\n  Run: cd apps/{fe.name} && npx expo start"
        )

    typer.echo("\nTo tear down: kreator dev --destroy")


def _prepare_for_local_dev(project_dir: Path) -> None:
    """Patch project files so the in-cluster git server and ArgoCD use local-dev settings."""
    patch_claims_for_env(project_dir, "local")
    patch_argocd_repo_url(project_dir, GIT_SERVER_URL)


def _ensure_git_committed(project_dir: Path) -> None:
    """Make sure the project has at least one commit so the git server can clone it."""
    from kreator.core.shell import run

    result = run(
        ["git", "-C", str(project_dir), "rev-parse", "HEAD"],
        capture=True,
        check=False,
    )
    if result.returncode != 0:
        logger.info("creating initial git commit")
        run(["git", "-C", str(project_dir), "add", "-A"])
        run(["git", "-C", str(project_dir), "commit", "-m", "initial scaffold"])
        return
    status = run(
        ["git", "-C", str(project_dir), "status", "--porcelain"],
        capture=True,
        check=False,
    )
    if status.returncode == 0 and status.stdout.strip():
        logger.info("committing pending changes for local dev")
        run(["git", "-C", str(project_dir), "add", "-A"])
        run(["git", "-C", str(project_dir), "commit", "-m", "prepare for local dev"])


def _preload_images() -> None:
    """Push common images to the local registry so kind nodes can pull them."""
    from kreator.core.registry import REGISTRY_PORT
    from kreator.core.shell import run

    images = ["postgres:16-alpine"]
    for image in images:
        result = run(
            ["docker", "image", "inspect", image],
            capture=True,
            check=False,
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
