import json
import logging
import socket
import time
from collections.abc import Callable
from pathlib import Path

from kreator.core.shell import run

logger = logging.getLogger(__name__)

CLUSTER_PREFIX = "kreator-"
REGISTRY_NAME = "kreator-registry"
REGISTRY_PORT = 5001

PROJECT_MOUNT_PATH = "/mnt/project"

# Each project gets its own kind cluster with its own host ports so multiple
# projects can run side by side. Ports are allocated in pairs (http, https)
# stepping from these bases and persisted per cluster in STATE_FILE.
BASE_HTTP_PORT = 9080
BASE_HTTPS_PORT = 9443
PORT_STEP = 10
STATE_FILE = Path.home() / ".kreator" / "clusters.json"


def cluster_name(slug: str) -> str:
    """The kind cluster name for a project slug."""
    return f"{CLUSTER_PREFIX}{slug}"


def list_kreator_clusters() -> list[str]:
    result = run(["kind", "get", "clusters"], capture=True, check=False)
    return [c for c in result.stdout.split() if c.startswith(CLUSTER_PREFIX)]


def cluster_exists(name: str) -> bool:
    result = run(["kind", "get", "clusters"], capture=True, check=False)
    return name in result.stdout.split()


def _load_state(state_file: Path) -> dict:
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_state(state_file: Path, state: dict) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2, sort_keys=True))


def _port_available(port: int) -> bool:
    """True if the host port can be bound (not already in use by any process)."""
    for host in ("0.0.0.0", "127.0.0.1"):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
            except OSError:
                return False
    return True


def allocate_ports(
    name: str,
    state_file: Path = STATE_FILE,
    port_available: Callable[[int], bool] | None = None,
) -> tuple[int, int]:
    """Return the (http, https) host ports for a cluster, allocating on first use.

    Allocation is stable: once a cluster has ports they are reused. New clusters
    get the lowest port pair that is neither recorded for another cluster nor
    already bound by some other process on the host, so ports freed by a
    destroyed cluster (or never taken) are reused.
    """
    if port_available is None:
        port_available = _port_available

    state = _load_state(state_file)
    if name in state:
        entry = state[name]
        return entry["http"], entry["https"]

    used = {entry["http"] for entry in state.values()}
    http = BASE_HTTP_PORT
    while True:
        https = BASE_HTTPS_PORT + (http - BASE_HTTP_PORT)
        if http not in used and port_available(http) and port_available(https):
            break
        http += PORT_STEP
    state[name] = {"http": http, "https": https}
    _save_state(state_file, state)
    return http, https


def release_ports(name: str, state_file: Path = STATE_FILE) -> None:
    state = _load_state(state_file)
    if name in state:
        del state[name]
        _save_state(state_file, state)


def use_cluster_context(name: str) -> None:
    """Point kubectl/helm at this cluster's context for the rest of the run."""
    run(["kubectl", "config", "use-context", f"kind-{name}"], check=False)


def create_cluster(
    name: str,
    http_port: int = BASE_HTTP_PORT,
    https_port: int = BASE_HTTPS_PORT,
    project_dir: Path | None = None,
) -> None:
    if cluster_exists(name):
        logger.info("cluster %s already exists", name)
        use_cluster_context(name)
        return

    mount_block = ""
    worker_mount = ""
    if project_dir:
        mount = f"""
    extraMounts:
      - hostPath: {project_dir}
        containerPath: {PROJECT_MOUNT_PATH}
        readOnly: true"""
        mount_block = mount
        worker_mount = mount

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
        hostPort: {http_port}
        protocol: TCP
      - containerPort: 443
        hostPort: {https_port}
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

    config_path = Path(f"/tmp/kreator-kind-config-{name}.yaml")
    config_path.write_text(config_yaml)

    logger.info("creating kind cluster: %s (http %d, https %d)", name, http_port, https_port)
    run(["kind", "create", "cluster", "--name", name, "--config", str(config_path)])
    config_path.unlink(missing_ok=True)

    use_cluster_context(name)
    _connect_registry_to_cluster()
    _configure_registry_on_nodes(name)


def delete_cluster(name: str) -> None:
    if not cluster_exists(name):
        logger.info("cluster %s does not exist", name)
        return

    logger.info("deleting kind cluster: %s", name)
    run(["kind", "delete", "cluster", "--name", name])


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


def _configure_registry_on_nodes(name: str) -> None:
    """Configure containerd on each kind node to use the local registry via certs.d."""
    registry_internal_port = 5000
    hosts_toml = (
        f'server = "http://{REGISTRY_NAME}:{registry_internal_port}"\n'
        f"\n"
        f'[host."http://{REGISTRY_NAME}:{registry_internal_port}"]\n'
        f'  capabilities = ["pull", "resolve", "push"]\n'
    )
    certs_dir = f"/etc/containerd/certs.d/localhost:{REGISTRY_PORT}"
    config_patch = (
        '\n[plugins."io.containerd.cri.v1.images".registry]\n'
        '  config_path = "/etc/containerd/certs.d"\n'
    )
    result = run(
        [
            "docker",
            "ps",
            "--filter",
            f"label=io.x-k8s.kind.cluster={name}",
            "--format",
            "{{.Names}}",
        ],
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
