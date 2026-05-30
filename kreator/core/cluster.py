import logging
import subprocess
import time
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

CLUSTER_NAME = "kreator-dev"
REGISTRY_NAME = "kreator-registry"
REGISTRY_PORT = 5001


def _run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            check=check,
            capture_output=capture,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        msg = f"Command failed: {' '.join(cmd)}"
        if e.stderr:
            msg += f"\n{e.stderr.strip()}"
        raise RuntimeError(msg) from e
    except FileNotFoundError:
        raise RuntimeError(f"Command not found: {cmd[0]}. Is it installed and on your PATH?")


def cluster_exists() -> bool:
    result = _run(["kind", "get", "clusters"], capture=True, check=False)
    return CLUSTER_NAME in result.stdout.split()


def create_cluster() -> None:
    if cluster_exists():
        logger.info("cluster %s already exists", CLUSTER_NAME)
        return

    kind_config = {
        "kind": "Cluster",
        "apiVersion": "kind.x-k8s.io/v1alpha4",
        "containerdConfigPatches": [
            f'[plugins."io.containerd.grpc.v1.cri".registry.mirrors.'
            f'"localhost:{REGISTRY_PORT}"]\n'
            f'  endpoint = ["http://{REGISTRY_NAME}:{REGISTRY_PORT}"]'
        ],
        "nodes": [
            {
                "role": "control-plane",
                "kubeadmConfigPatches": [
                    "kind: InitConfiguration\nnodeRegistration:\n  kubeletExtraArgs:\n"
                    '    node-labels: "ingress-ready=true"\n',
                ],
                "extraPortMappings": [
                    {"containerPort": 80, "hostPort": 9080, "protocol": "TCP"},
                    {"containerPort": 443, "hostPort": 9443, "protocol": "TCP"},
                ],
            },
            {"role": "worker"},
            {"role": "worker"},
        ],
    }

    config_path = Path("/tmp/kreator-kind-config.yaml")
    config_path.write_text(yaml.dump(kind_config))

    logger.info("creating kind cluster: %s", CLUSTER_NAME)
    _run(["kind", "create", "cluster", "--name", CLUSTER_NAME, "--config", str(config_path)])
    config_path.unlink(missing_ok=True)

    _connect_registry_to_cluster()


def delete_cluster() -> None:
    if not cluster_exists():
        logger.info("cluster %s does not exist", CLUSTER_NAME)
        return

    logger.info("deleting kind cluster: %s", CLUSTER_NAME)
    _run(["kind", "delete", "cluster", "--name", CLUSTER_NAME])


def _connect_registry_to_cluster() -> None:
    result = _run(
        ["docker", "inspect", "-f", "{{.State.Running}}", REGISTRY_NAME],
        capture=True,
        check=False,
    )
    if "true" not in result.stdout:
        return

    network = "kind"
    result = _run(
        ["docker", "inspect", "-f", "{{json .NetworkSettings.Networks}}", REGISTRY_NAME],
        capture=True,
        check=False,
    )
    if network not in result.stdout:
        _run(["docker", "network", "connect", network, REGISTRY_NAME], check=False)


def wait_for_cluster_ready(timeout: int = 120) -> None:
    logger.info("waiting for cluster nodes to be ready")
    start = time.time()
    while time.time() - start < timeout:
        result = _run(
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
            if all(s == "True" for s in statuses) and len(statuses) >= 3:
                logger.info("all nodes ready")
                return
        time.sleep(3)
    raise RuntimeError(f"Cluster nodes not ready after {timeout}s")
