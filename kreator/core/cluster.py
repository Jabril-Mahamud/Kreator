import subprocess
import time
from pathlib import Path

import typer

CLUSTER_NAME = "kreator-dev"
PROJECT_MOUNT_PATH = "/mnt/project"


def _kind_config(project_dir: Path | None = None) -> str:
    mount_block = ""
    if project_dir:
        resolved = project_dir.resolve()
        mount_block = (
            f"    extraMounts:\n"
            f"      - hostPath: {resolved}\n"
            f"        containerPath: {PROJECT_MOUNT_PATH}\n"
            f"        readOnly: true\n"
        )

    return (
        "kind: Cluster\n"
        "apiVersion: kind.x-k8s.io/v1alpha4\n"
        "nodes:\n"
        "  - role: control-plane\n"
        "    kubeadmConfigPatches:\n"
        "      - |\n"
        "        kind: InitConfiguration\n"
        "        nodeRegistration:\n"
        "          kubeletExtraArgs:\n"
        '            node-labels: "ingress-ready=true"\n'
        "    extraPortMappings:\n"
        "      - containerPort: 80\n"
        "        hostPort: 80\n"
        "        protocol: TCP\n"
        "      - containerPort: 443\n"
        "        hostPort: 443\n"
        "        protocol: TCP\n"
        f"{mount_block}"
        "  - role: worker\n"
        f"{mount_block}"
        "  - role: worker\n"
        f"{mount_block}"
        "containerdConfigPatches:\n"
        "  - |-\n"
        '    [plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:5001"]\n'
        '      endpoint = ["http://kind-registry:5000"]\n'
    )


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def cluster_exists() -> bool:
    result = _run(["kind", "get", "clusters"], check=False)
    return CLUSTER_NAME in result.stdout.split()


def create_cluster(project_dir: Path | None = None) -> None:
    if cluster_exists():
        typer.echo(f"Cluster '{CLUSTER_NAME}' already exists, reusing it")
        return

    typer.echo(f"Creating Kind cluster '{CLUSTER_NAME}'...")
    config = _kind_config(project_dir)
    subprocess.run(
        ["kind", "create", "cluster", "--name", CLUSTER_NAME, "--config", "-"],
        input=config,
        text=True,
        check=True,
    )
    typer.echo("Cluster created")


def delete_cluster() -> None:
    if not cluster_exists():
        typer.echo(f"Cluster '{CLUSTER_NAME}' does not exist, nothing to delete")
        return

    typer.echo(f"Deleting Kind cluster '{CLUSTER_NAME}'...")
    subprocess.run(
        ["kind", "delete", "cluster", "--name", CLUSTER_NAME],
        check=True,
        capture_output=True,
        text=True,
    )
    typer.echo("Cluster deleted")


def get_kubeconfig_context() -> str:
    return f"kind-{CLUSTER_NAME}"


def wait_for_nodes_ready(timeout: int = 120) -> None:
    typer.echo("Waiting for nodes to be ready...")
    ctx = get_kubeconfig_context()
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = _run(
            [
                "kubectl",
                "--context",
                ctx,
                "get",
                "nodes",
                "-o",
                "jsonpath={.items[*].status.conditions[-1].type}",
            ],
            check=False,
        )
        if result.returncode == 0:
            conditions = result.stdout.strip().split()
            if all(c == "Ready" for c in conditions) and len(conditions) >= 3:
                typer.echo("All nodes ready")
                return
        time.sleep(3)
    raise RuntimeError(f"Nodes not ready after {timeout}s")
