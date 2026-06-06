import logging
import time
from pathlib import Path

from kreator.core.shell import run

logger = logging.getLogger(__name__)

CLUSTER_NAME = "kreator-dev"
REGISTRY_NAME = "kreator-registry"
REGISTRY_PORT = 5001


def cluster_exists() -> bool:
    result = run(["kind", "get", "clusters"], capture=True, check=False)
    return CLUSTER_NAME in result.stdout.split()


PROJECT_MOUNT_PATH = "/mnt/project"


def create_cluster(project_dir: Path | None = None) -> None:
    if cluster_exists():
        logger.info("cluster %s already exists", CLUSTER_NAME)
        return

    mount_block = ""
    if project_dir:
        mount_block = f"""
    extraMounts:
      - hostPath: {project_dir}
        containerPath: {PROJECT_MOUNT_PATH}
        readOnly: true"""

    worker_mount = ""
    if project_dir:
        worker_mount = f"""
    extraMounts:
      - hostPath: {project_dir}
        containerPath: {PROJECT_MOUNT_PATH}
        readOnly: true"""

    config_yaml = f"""\
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
      - |
        kind: KubeletConfiguration
        serializeImagePulls: false
        maxParallelImagePulls: 5
    extraPortMappings:
      - containerPort: 80
        hostPort: 9080
        protocol: TCP
      - containerPort: 443
        hostPort: 9443
        protocol: TCP{mount_block}
  - role: worker
    kubeadmConfigPatches:
      - |
        kind: JoinConfiguration
        nodeRegistration:
          kubeletExtraArgs: {{}}
      - |
        kind: KubeletConfiguration
        serializeImagePulls: false
        maxParallelImagePulls: 5{worker_mount}
  - role: worker
    kubeadmConfigPatches:
      - |
        kind: JoinConfiguration
        nodeRegistration:
          kubeletExtraArgs: {{}}
      - |
        kind: KubeletConfiguration
        serializeImagePulls: false
        maxParallelImagePulls: 5{worker_mount}
"""

    config_path = Path("/tmp/kreator-kind-config.yaml")
    config_path.write_text(config_yaml)

    logger.info("creating kind cluster: %s", CLUSTER_NAME)
    run(["kind", "create", "cluster", "--name", CLUSTER_NAME, "--config", str(config_path)])
    config_path.unlink(missing_ok=True)

    _connect_registry_to_cluster()
    _configure_registry_on_nodes()


def delete_cluster() -> None:
    if not cluster_exists():
        logger.info("cluster %s does not exist", CLUSTER_NAME)
        return

    logger.info("deleting kind cluster: %s", CLUSTER_NAME)
    run(["kind", "delete", "cluster", "--name", CLUSTER_NAME])


def _connect_registry_to_cluster() -> None:
    result = run(
        ["docker", "inspect", "-f", "{{.State.Running}}", REGISTRY_NAME],
        capture=True,
        check=False,
    )
    if "true" not in result.stdout:
        return

    network = "kind"
    result = run(
        ["docker", "inspect", "-f", "{{json .NetworkSettings.Networks}}", REGISTRY_NAME],
        capture=True,
        check=False,
    )
    if network not in result.stdout:
        run(["docker", "network", "connect", network, REGISTRY_NAME], check=False)


def _configure_registry_on_nodes() -> None:
    """Configure containerd on each kind node to use the local registry via certs.d."""
    registry_internal_port = 5000
    hosts_toml = (
        f'server = "http://{REGISTRY_NAME}:{registry_internal_port}"\n'
        f'\n'
        f'[host."http://{REGISTRY_NAME}:{registry_internal_port}"]\n'
        f'  capabilities = ["pull", "resolve", "push"]\n'
    )
    certs_dir = f"/etc/containerd/certs.d/localhost:{REGISTRY_PORT}"
    config_patch = (
        '\n[plugins."io.containerd.cri.v1.images".registry]\n'
        '  config_path = "/etc/containerd/certs.d"\n'
    )
    result = run(
        ["docker", "ps", "--filter", f"label=io.x-k8s.kind.cluster={CLUSTER_NAME}",
         "--format", "{{.Names}}"],
        capture=True,
    )
    nodes = result.stdout.strip().split()
    for node in nodes:
        run(["docker", "exec", node, "mkdir", "-p", certs_dir])
        run(
            ["docker", "exec", "-i", node, "bash", "-c", f"cat > {certs_dir}/hosts.toml"],
            input=hosts_toml,
        )
        check_cmd = (
            "grep -q 'cri.v1.images' /etc/containerd/config.toml"
            " || cat >> /etc/containerd/config.toml"
        )
        run(
            ["docker", "exec", "-i", node, "bash", "-c", check_cmd],
            input=config_patch,
        )
        run(["docker", "exec", node, "systemctl", "restart", "containerd"])
    logger.info("configured local registry on %d nodes", len(nodes))


def wait_for_cluster_ready(timeout: int = 120) -> None:
    logger.info("waiting for cluster nodes to be ready")
    start = time.time()
    while time.time() - start < timeout:
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
            if all(s == "True" for s in statuses) and len(statuses) >= 3:
                logger.info("all nodes ready")
                return
        time.sleep(3)
    raise RuntimeError(f"Cluster nodes not ready after {timeout}s")
