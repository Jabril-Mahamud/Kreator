import logging
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def _run(
    cmd: list[str],
    check: bool = True,
    capture: bool = False,
    input: str | None = None,
) -> subprocess.CompletedProcess:
    try:
        kwargs: dict = {"check": check, "text": True}
        if input is not None:
            kwargs["input"] = input
            kwargs["capture_output"] = True
        elif capture:
            kwargs["capture_output"] = True
        return subprocess.run(cmd, **kwargs)
    except subprocess.CalledProcessError as e:
        msg = f"Command failed: {' '.join(cmd)}"
        if e.stderr:
            msg += f"\n{e.stderr.strip()}"
        raise RuntimeError(msg) from e
    except FileNotFoundError:
        raise RuntimeError(f"Command not found: {cmd[0]}. Is it installed and on your PATH?")


def _wait_for_deployment(name: str, namespace: str, timeout: int = 180) -> None:
    logger.info("waiting for deployment %s/%s", namespace, name)
    _run(
        [
            "kubectl",
            "rollout",
            "status",
            f"deployment/{name}",
            "-n",
            namespace,
            f"--timeout={timeout}s",
        ]
    )


def _wait_for_crd(crd_name: str, timeout: int = 120) -> None:
    start = time.time()
    while time.time() - start < timeout:
        result = _run(
            ["kubectl", "get", "crd", crd_name],
            capture=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(3)
    raise RuntimeError(f"CRD {crd_name} not available after {timeout}s")


def install_crossplane() -> None:
    logger.info("installing crossplane")

    _run(["kubectl", "create", "namespace", "crossplane-system"], check=False)

    _run(
        [
            "helm",
            "repo",
            "add",
            "crossplane-stable",
            "https://charts.crossplane.io/stable",
        ],
        check=False,
    )
    _run(["helm", "repo", "update"])

    _run(
        [
            "helm",
            "upgrade",
            "--install",
            "crossplane",
            "crossplane-stable/crossplane",
            "--namespace",
            "crossplane-system",
            "--wait",
            "--timeout",
            "3m",
        ]
    )

    _wait_for_deployment("crossplane", "crossplane-system")

    _install_crossplane_provider_kubernetes()


def _install_crossplane_provider_kubernetes() -> None:
    provider_yaml = """
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-kubernetes
spec:
  package: xpkg.upbound.io/crossplane-contrib/provider-kubernetes:v0.14.1
"""
    _run(
        ["kubectl", "apply", "-f", "-"],
        check=True,
        input=provider_yaml,
    )

    _wait_for_crd("objects.kubernetes.crossplane.io")

    sa_binding = """
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: provider-kubernetes-admin
subjects:
  - kind: ServiceAccount
    name: provider-kubernetes
    namespace: crossplane-system
roleRef:
  kind: ClusterRole
  name: cluster-admin
  apiGroup: rbac.authorization.k8s.io
"""
    time.sleep(5)
    _run(["kubectl", "apply", "-f", "-"], input=sa_binding, check=False)


def install_argocd() -> None:
    logger.info("installing argocd")

    _run(["kubectl", "create", "namespace", "argocd"], check=False)
    _run(
        [
            "kubectl",
            "apply",
            "-n",
            "argocd",
            "-f",
            "https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml",
        ]
    )

    _wait_for_deployment("argocd-server", "argocd", timeout=240)

    _run(
        [
            "kubectl",
            "patch",
            "svc",
            "argocd-server",
            "-n",
            "argocd",
            "-p",
            '{"spec": {"type": "NodePort"}}',
        ],
        check=False,
    )


def install_ingress_nginx() -> None:
    logger.info("installing ingress-nginx")

    _run(
        [
            "helm",
            "repo",
            "add",
            "ingress-nginx",
            "https://kubernetes.github.io/ingress-nginx",
        ],
        check=False,
    )
    _run(["helm", "repo", "update"])

    _run(
        [
            "helm",
            "upgrade",
            "--install",
            "ingress-nginx",
            "ingress-nginx/ingress-nginx",
            "--namespace",
            "ingress-nginx",
            "--create-namespace",
            "--set",
            "controller.hostNetwork=true",
            "--set",
            "controller.kind=DaemonSet",
            "--set",
            "controller.service.type=NodePort",
            "--set",
            "controller.nodeSelector.ingress-ready=true",
            "--wait",
            "--timeout",
            "3m",
        ]
    )


def install_sealed_secrets() -> None:
    logger.info("installing sealed-secrets")

    _run(
        [
            "helm",
            "repo",
            "add",
            "sealed-secrets",
            "https://bitnami-labs.github.io/sealed-secrets",
        ],
        check=False,
    )
    _run(["helm", "repo", "update"])

    _run(
        [
            "helm",
            "upgrade",
            "--install",
            "sealed-secrets",
            "sealed-secrets/sealed-secrets",
            "--namespace",
            "kube-system",
            "--wait",
            "--timeout",
            "3m",
        ]
    )


def apply_manifests(project_dir: Path) -> None:
    """Apply Crossplane XRDs, provider configs, compositions, claims, and secrets."""
    infra_dir = project_dir / "infrastructure"
    secrets_dir = project_dir / "secrets" / "sealed"

    xrds = infra_dir / "xrds"
    if xrds.is_dir():
        logger.info("applying crossplane xrds")
        _run(["kubectl", "apply", "-f", str(xrds)])
        time.sleep(5)

    provider_configs = infra_dir / "provider-configs"
    if provider_configs.is_dir():
        logger.info("applying provider configs")
        for f in provider_configs.glob("*.yaml"):
            _run(["kubectl", "apply", "-f", str(f)], check=False)
        time.sleep(3)

    compositions_dir = infra_dir / "compositions" / "local"
    if compositions_dir.is_dir():
        logger.info("applying local compositions")
        _run(["kubectl", "apply", "-f", str(compositions_dir)])
        time.sleep(3)

    if secrets_dir.is_dir():
        logger.info("applying secrets")
        _run(["kubectl", "apply", "-f", str(secrets_dir)])

    claims = infra_dir / "claims"
    if claims.is_dir():
        logger.info("applying crossplane claims")
        _run(["kubectl", "apply", "-f", str(claims)])


def setup_argocd_apps(project_dir: Path) -> None:
    """Apply ArgoCD Application CRs."""
    argocd_dir = project_dir / "deploy" / "argocd"

    root_app = argocd_dir / "root-app.yaml"
    if root_app.exists():
        logger.info("applying argocd root app")
        _run(["kubectl", "apply", "-f", str(root_app)])

    apps_dir = argocd_dir / "apps"
    if apps_dir.is_dir():
        logger.info("applying argocd apps")
        _run(["kubectl", "apply", "-f", str(apps_dir)])


def install_helm_releases(project_dir: Path) -> None:
    """Install all helm charts found in deploy/helm/."""
    helm_dir = project_dir / "deploy" / "helm"
    if not helm_dir.is_dir():
        return

    for chart_dir in sorted(helm_dir.iterdir()):
        if not chart_dir.is_dir():
            continue
        logger.info("installing %s helm chart", chart_dir.name)
        _run(
            [
                "helm",
                "upgrade",
                "--install",
                chart_dir.name,
                str(chart_dir),
                "--namespace",
                "default",
                "--wait",
                "--timeout",
                "3m",
            ]
        )
