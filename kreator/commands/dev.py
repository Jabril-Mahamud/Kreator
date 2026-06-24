import logging
import os
import sys
from pathlib import Path

import typer

from kreator.core.cluster import (
    allocate_ports,
    cluster_exists,
    cluster_name,
    create_cluster,
    delete_cluster,
    list_kreator_clusters,
    release_ports,
    use_cluster_context,
    wait_for_cluster_ready,
)
from kreator.core.config import KreatorConfig, load_config
from kreator.core.platform import (
    DEV_BRANCH,
    GIT_SERVER_URL,
    apply_manifests,
    check_prerequisites,
    deploy_git_server,
    get_argocd_password,
    hard_refresh_apps,
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
    refresh: bool = typer.Option(
        False,
        "--refresh",
        help="Rebuild images and redeploy to a running cluster without the full setup",
    ),
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

    if refresh:
        _refresh(project_dir, config)
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


def _refresh(project_dir: Path, config: KreatorConfig) -> None:
    """Redeploy code changes to an already-running cluster without a full setup.

    Rebuilds and re-pins images, recreates the in-cluster git server so it serves
    the new commit, and hard-refreshes ArgoCD so the change deploys. This is the
    lightweight edit/redeploy loop; it skips cluster creation and platform
    installs (ISSUES.md #3).
    """
    name = cluster_name(config.name)
    if not cluster_exists(name):
        typer.echo(
            f"Error: cluster '{name}' is not running. Run 'kreator dev' first.",
            err=True,
        )
        raise typer.Exit(1)

    typer.echo(f"Refreshing local dev environment for '{config.name}'...")
    use_cluster_context(name)
    _prepare_for_local_dev(project_dir)

    typer.echo("[1/3] Building and pushing images, sealing secrets...")
    start_registry()
    run(["kubectl", "create", "namespace", config.name], check=False)
    seal_secrets(project_dir)
    _build_and_pin_images(project_dir, config)

    typer.echo("[2/3] Refreshing in-cluster git server...")
    deploy_git_server()

    typer.echo("[3/3] Triggering ArgoCD hard refresh...")
    hard_refresh_apps(config.name)

    http_port, _ = allocate_ports(name)
    typer.echo("\nRefresh complete. ArgoCD is syncing the new revision.")
    for fe in config.web_frontends:
        typer.echo(f"  {fe.name}: http://{fe.name}.localhost:{http_port}")
    typer.echo(f"  Backend:  http://api.localhost:{http_port}")


def _setup(project_dir: Path, config: KreatorConfig, with_observability: bool) -> None:
    typer.echo(f"Setting up local dev environment for '{config.name}'...")

    errors = check_prerequisites()
    if errors:
        typer.echo("Missing prerequisites:", err=True)
        for err in errors:
            typer.echo(f"  - {err}", err=True)
        raise typer.Exit(1)

    _prepare_for_local_dev(project_dir)

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
    seal_secrets(project_dir)
    _build_and_pin_images(project_dir, config)

    typer.echo("[5/6] Applying infrastructure (XRDs, compositions, claims)...")
    apply_manifests(project_dir)
    wait_for_db_ready(config.name, namespace=config.name)

    typer.echo("[6/6] Deploying git server and configuring ArgoCD...")
    deploy_git_server()
    setup_argocd_apps(project_dir, config.name)

    if with_observability:
        typer.echo("Waiting for observability stack (ArgoCD-managed)...")
        _install_observability(config.name)

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


def _snapshot_dev_branch(project_dir: Path, message: str) -> str:
    """Snapshot the current working tree onto the local-dev branch, return its short SHA.

    The commit is built with a throwaway index and `git commit-tree`, so the
    user's branch, HEAD, working tree, and index are never touched. The in-cluster
    git server serves this branch as HEAD, so local dev never pollutes the user's
    real branch (ISSUES.md #4) while still giving ArgoCD a clean committed source.
    """
    git = ["git", "-C", str(project_dir)]
    # Isolate staging in a throwaway index so `git add -A` leaves the user's index
    # untouched.
    tmp_index = project_dir / ".git" / "kreator-dev-index"
    tmp_index.unlink(missing_ok=True)
    env = {**os.environ, "GIT_INDEX_FILE": str(tmp_index)}
    try:
        run(git + ["add", "-A"], env=env)
        tree = run(git + ["write-tree"], capture=True, env=env).stdout.strip()
        commit_cmd = git + ["commit-tree", tree, "-m", message]
        parent = _ref_commit(project_dir, f"refs/heads/{DEV_BRANCH}") or _ref_commit(
            project_dir, "HEAD"
        )
        if parent:
            commit_cmd += ["-p", parent]
        # commit-tree needs a committer identity; fall back to a generic one only
        # when the user hasn't configured git, so we never error on a fresh setup.
        commit_env = dict(os.environ)
        if not _git_config(project_dir, "user.name"):
            commit_env["GIT_AUTHOR_NAME"] = commit_env["GIT_COMMITTER_NAME"] = "kreator"
        if not _git_config(project_dir, "user.email"):
            commit_env["GIT_AUTHOR_EMAIL"] = commit_env["GIT_COMMITTER_EMAIL"] = "kreator@localhost"
        commit = run(commit_cmd, capture=True, env=commit_env).stdout.strip()
        run(git + ["update-ref", f"refs/heads/{DEV_BRANCH}", commit])
        return run(git + ["rev-parse", "--short", commit], capture=True).stdout.strip()
    finally:
        tmp_index.unlink(missing_ok=True)


def _ref_commit(project_dir: Path, ref: str) -> str | None:
    """Resolve a git ref to a full commit SHA, or None if it doesn't exist."""
    result = run(
        ["git", "-C", str(project_dir), "rev-parse", "--verify", "--quiet", ref],
        capture=True,
        check=False,
    )
    sha = result.stdout.strip()
    return sha or None


def _git_config(project_dir: Path, key: str) -> str:
    """Return a git config value for the project, or empty string if unset."""
    result = run(
        ["git", "-C", str(project_dir), "config", "--get", key],
        capture=True,
        check=False,
    )
    return result.stdout.strip()


def _build_and_pin_images(project_dir: Path, config: KreatorConfig) -> str:
    """Build/push images under an immutable SHA tag and pin helm values to it.

    The :latest tag never changes the manifest, so ArgoCD/Kubernetes won't roll
    the pods on a rebuild. Snapshotting the source to the dev branch first, then
    tagging images with that commit's short SHA, makes every code change show up
    as a changed image.tag so ArgoCD redeploys on its own. Returns the image tag.
    """
    image_tag = _snapshot_dev_branch(project_dir, "kreator local dev: source")
    build_and_push(f"{config.name}-backend", str(project_dir / "apps" / "backend"), tag=image_tag)
    for fe in config.web_frontends:
        build_and_push(
            f"{config.name}-{fe.name}", str(project_dir / "apps" / fe.name), tag=image_tag
        )
    _set_image_tags(project_dir, config, image_tag)
    _snapshot_dev_branch(project_dir, f"kreator local dev: pin images to {image_tag}")
    return image_tag


def _set_image_tags(project_dir: Path, config: KreatorConfig, tag: str) -> None:
    """Pin image.tag to an immutable SHA in every web workload's helm values."""
    import re

    charts = ["backend"] + [fe.name for fe in config.web_frontends]
    for chart in charts:
        values = project_dir / "deploy" / "helm" / chart / "values.yaml"
        if not values.exists():
            continue
        text = values.read_text()
        # The image tag is the first `tag:` key in the generated values file.
        new_text = re.sub(
            r"^(\s*)tag:.*$",
            rf"\g<1>tag: {tag}",
            text,
            count=1,
            flags=re.MULTILINE,
        )
        if new_text != text:
            values.write_text(new_text)


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


def _install_observability(project_name: str) -> None:
    from kreator.core.observability import install_observability_stack

    install_observability_stack(project_name)
