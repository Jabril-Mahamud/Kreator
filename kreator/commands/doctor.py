import logging
import sys
from pathlib import Path

import typer

from kreator.core.config import load_config
from kreator.core.platform import check_prerequisites
from kreator.core.shell import run

logger = logging.getLogger(__name__)


def doctor() -> None:
    """Check prerequisites and cluster health."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stdout,
    )

    typer.echo("Checking prerequisites...\n")
    _check_tools()

    project_dir = Path.cwd()
    config_path = project_dir / "kreator.yaml"
    if not config_path.exists():
        typer.echo("\nNot in a kreator project directory, skipping cluster checks.")
        return

    config = load_config(config_path)
    typer.echo(f"\nChecking cluster health for '{config.name}'...\n")
    _check_cluster(config.name)


def _check_tools() -> None:
    errors = check_prerequisites()
    if not errors:
        _pass("docker, kind, kubectl, helm")
    else:
        for err in errors:
            _fail(err)


def _check_cluster(name: str) -> None:
    result = run(["kind", "get", "clusters"], capture=True, check=False)
    if "kreator-dev" not in result.stdout.split():
        _fail("Kind cluster 'kreator-dev' not running")
        return
    _pass("Kind cluster running")

    result = run(
        [
            "kubectl",
            "get",
            "nodes",
            "-o",
            "jsonpath={.items[*].status.conditions[?(@.type=='Ready')].status}",
        ],
        capture=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout:
        statuses = result.stdout.split()
        if all(s == "True" for s in statuses):
            _pass(f"All {len(statuses)} nodes ready")
        else:
            _fail(f"Some nodes not ready: {result.stdout}")
    else:
        _fail("Could not query node status")

    _check_helm_release("crossplane", "crossplane-system")
    _check_helm_release("ingress-nginx", "ingress-nginx")
    _check_helm_release("sealed-secrets", "kube-system")

    _check_deployment("argocd-server", "argocd")

    result = run(
        ["kubectl", "get", "crd", "databases.kreator.dev"],
        capture=True,
        check=False,
    )
    if result.returncode == 0:
        _pass("XRD CRD registered (databases.kreator.dev)")
    else:
        _fail("XRD CRD not registered (databases.kreator.dev)")

    result = run(
        ["kubectl", "get", "compositions.apiextensions.crossplane.io"],
        capture=True,
        check=False,
    )
    if result.returncode == 0 and "local-database" in result.stdout:
        _pass("Local database composition exists")
    else:
        _fail("Local database composition missing")

    result = run(
        ["kubectl", "get", f"databases.kreator.dev/{name}-db", "-o", "name"],
        capture=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        _pass(f"Database claim applied ({name}-db)")
    else:
        _fail(f"Database claim not found ({name}-db)")

    result = run(
        ["kubectl", "get", "statefulset", f"{name}-db", "-o", "jsonpath={.status.readyReplicas}"],
        capture=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip() == "1":
        _pass("Database pod ready")
    else:
        _fail("Database pod not ready")

    result = run(
        [
            "kubectl",
            "get",
            "pods",
            "-l",
            f"app.kubernetes.io/name={name}-backend",
            "-o",
            "jsonpath={.items[*].status.containerStatuses[*].ready}",
        ],
        capture=True,
        check=False,
    )
    if result.returncode == 0 and "true" in result.stdout:
        _pass("Backend pod ready")
    else:
        _fail("Backend pod not ready")


def _check_helm_release(release: str, namespace: str) -> None:
    result = run(
        ["helm", "status", release, "-n", namespace],
        capture=True,
        check=False,
    )
    if result.returncode == 0:
        _pass(f"Helm release: {release} ({namespace})")
    else:
        _fail(f"Helm release: {release} ({namespace})")


def _check_deployment(name: str, namespace: str) -> None:
    result = run(
        [
            "kubectl",
            "get",
            "deployment",
            name,
            "-n",
            namespace,
            "-o",
            "jsonpath={.status.readyReplicas}",
        ],
        capture=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        _pass(f"Deployment: {name} ({namespace})")
    else:
        _fail(f"Deployment: {name} ({namespace})")


def _pass(msg: str) -> None:
    typer.echo(f"  [ok] {msg}")


def _fail(msg: str) -> None:
    typer.echo(f"  [!!] {msg}")
