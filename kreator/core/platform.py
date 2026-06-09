import logging
import shutil
import time
from pathlib import Path

import yaml

from kreator.core.shell import run

logger = logging.getLogger(__name__)


def _wait_for_deployment(name: str, namespace: str, timeout: int = 180) -> None:
    logger.info("waiting for deployment %s/%s", namespace, name)
    run(
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


def wait_for_crd(crd_name: str, timeout: int = 120) -> None:
    start = time.time()
    while time.time() - start < timeout:
        result = run(
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

    run(["kubectl", "create", "namespace", "crossplane-system"], check=False)

    run(
        [
            "helm",
            "repo",
            "add",
            "crossplane-stable",
            "https://charts.crossplane.io/stable",
        ],
        check=False,
    )
    run(["helm", "repo", "update"])

    run(
        [
            "helm",
            "upgrade",
            "--install",
            "crossplane",
            "crossplane-stable/crossplane",
            "--version",
            "1.20.9",
            "--namespace",
            "crossplane-system",
            "--wait",
            "--timeout",
            "8m",
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
    run(
        ["kubectl", "apply", "-f", "-"],
        check=True,
        input=provider_yaml,
    )

    wait_for_crd("objects.kubernetes.crossplane.io")

    time.sleep(10)
    result = run(
        [
            "kubectl",
            "get",
            "sa",
            "-n",
            "crossplane-system",
            "-o",
            "jsonpath={.items[*].metadata.name}",
        ],
        capture=True,
    )
    sa_name = "provider-kubernetes"
    for name in result.stdout.split():
        if name.startswith("provider-kubernetes-"):
            sa_name = name
            break

    sa_binding = f"""
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: provider-kubernetes-admin
subjects:
  - kind: ServiceAccount
    name: {sa_name}
    namespace: crossplane-system
roleRef:
  kind: ClusterRole
  name: cluster-admin
  apiGroup: rbac.authorization.k8s.io
"""
    run(["kubectl", "apply", "-f", "-"], input=sa_binding, check=False)


def install_argocd() -> None:
    logger.info("installing argocd")

    run(["kubectl", "create", "namespace", "argocd"], check=False)
    run(
        [
            "kubectl",
            "apply",
            "-n",
            "argocd",
            "--server-side",
            "--force-conflicts",
            "-f",
            "https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml",
        ]
    )

    run(
        [
            "kubectl",
            "patch",
            "configmap",
            "argocd-cmd-params-cm",
            "-n",
            "argocd",
            "-p",
            '{"data": {"server.insecure": "true",'
            ' "server.basehref": "/argocd",'
            ' "server.rootpath": "/argocd"}}',
        ],
        check=False,
    )

    try:
        _wait_for_deployment("argocd-server", "argocd", timeout=300)
    except RuntimeError:
        logger.warning("argocd-server not ready yet, it will become available in the background")

    run(
        ["kubectl", "rollout", "restart", "deployment/argocd-server", "-n", "argocd"],
        check=False,
    )

    ingress_yaml = """\
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: argocd-server
  namespace: argocd
spec:
  ingressClassName: nginx
  rules:
    - http:
        paths:
          - path: /argocd
            pathType: Prefix
            backend:
              service:
                name: argocd-server
                port:
                  number: 80
"""
    run(["kubectl", "apply", "-f", "-"], input=ingress_yaml)


def install_ingress_nginx() -> None:
    logger.info("installing ingress-nginx")

    run(
        [
            "helm",
            "repo",
            "add",
            "ingress-nginx",
            "https://kubernetes.github.io/ingress-nginx",
        ],
        check=False,
    )
    run(["helm", "repo", "update"])

    run(
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
            "--set-string",
            "controller.nodeSelector.ingress-ready=true",
            "--set",
            "controller.tolerations[0].key=node-role.kubernetes.io/control-plane",
            "--set",
            "controller.tolerations[0].operator=Exists",
            "--set",
            "controller.tolerations[0].effect=NoSchedule",
            "--wait",
            "--timeout",
            "8m",
        ]
    )


def install_sealed_secrets() -> None:
    logger.info("installing sealed-secrets")

    run(
        [
            "helm",
            "repo",
            "add",
            "sealed-secrets",
            "https://bitnami-labs.github.io/sealed-secrets",
        ],
        check=False,
    )
    run(["helm", "repo", "update"])

    run(
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
            "8m",
        ]
    )


def patch_claims_for_env(project_dir: Path, provider: str) -> None:
    """Rewrite compositionSelector.matchLabels.provider in all claim files on disk."""
    claims_dir = project_dir / "infrastructure" / "claims"
    if not claims_dir.is_dir():
        return
    for claim_file in claims_dir.glob("*.yaml"):
        doc = yaml.safe_load(claim_file.read_text())
        sel = doc.get("spec", {}).get("compositionSelector", {})
        labels = sel.get("matchLabels", {})
        if "provider" in labels:
            labels["provider"] = provider
            claim_file.write_text(yaml.dump(doc, default_flow_style=False))
            logger.info("patched %s: provider=%s", claim_file.name, provider)


def patch_argocd_repo_url(project_dir: Path, repo_url: str) -> None:
    """Rewrite spec.source.repoURL in all ArgoCD Application manifests on disk."""
    argocd_dir = project_dir / "deploy" / "argocd"
    if not argocd_dir.is_dir():
        return
    for app_file in argocd_dir.rglob("*.yaml"):
        doc = yaml.safe_load(app_file.read_text())
        source = doc.get("spec", {}).get("source", {})
        if "repoURL" in source:
            source["repoURL"] = repo_url
            app_file.write_text(yaml.dump(doc, default_flow_style=False))
            logger.info("patched %s: repoURL=%s", app_file.name, repo_url)


def apply_manifests(project_dir: Path) -> None:
    """Apply Crossplane XRDs, provider configs, compositions, and claims."""
    infra_dir = project_dir / "infrastructure"

    xrds = infra_dir / "xrds"
    if xrds.is_dir():
        logger.info("applying crossplane xrds")
        run(["kubectl", "apply", "-f", str(xrds)])
        wait_for_crd("databases.kreator.dev")

    local_provider_config = infra_dir / "provider-configs" / "local.yaml"
    if local_provider_config.exists():
        logger.info("applying local provider config")
        run(["kubectl", "apply", "-f", str(local_provider_config)], check=False)
        time.sleep(3)

    compositions_dir = infra_dir / "compositions" / "local"
    if compositions_dir.is_dir():
        logger.info("applying local compositions")
        run(["kubectl", "apply", "-f", str(compositions_dir)])
        time.sleep(3)

    claims = infra_dir / "claims"
    if claims.is_dir():
        logger.info("applying crossplane claims (provider=local)")
        for claim_file in claims.glob("*.yaml"):
            doc = yaml.safe_load(claim_file.read_text())
            sel = doc.get("spec", {}).get("compositionSelector", {})
            labels = sel.get("matchLabels", {})
            if labels.get("provider") and labels["provider"] != "local":
                labels["provider"] = "local"
            patched = yaml.dump(doc, default_flow_style=False)
            run(["kubectl", "apply", "-f", "-"], input=patched)
        result = run(
            ["kubectl", "get", "databases.kreator.dev", "-o", "name"],
            capture=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            logger.info("claims applied: %s", result.stdout.strip())
        else:
            logger.warning("database claims may not have been applied correctly")


def wait_for_db_ready(name: str, timeout: int = 180) -> None:
    """Wait for the Crossplane-managed database StatefulSet to have a ready pod."""
    sts_name = f"{name}-db"
    logger.info("waiting for database to be ready (%s)", sts_name)
    start = time.time()
    while time.time() - start < timeout:
        result = run(
            ["kubectl", "get", "statefulset", sts_name, "-o", "jsonpath={.status.readyReplicas}"],
            capture=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip() == "1":
            logger.info("database is ready")
            return
        time.sleep(5)
    logger.warning("database not ready after %ds, continuing anyway", timeout)


GIT_SERVER_URL = "git://git-server.default.svc/repo.git"


def deploy_git_server() -> None:
    """Deploy a lightweight git server that serves the project mounted at /mnt/project."""
    from kreator.core.cluster import PROJECT_MOUNT_PATH

    manifest = f"""\
apiVersion: v1
kind: Pod
metadata:
  name: git-server
  namespace: default
  labels:
    app: git-server
spec:
  containers:
    - name: git
      image: alpine/git:latest
      command: ["sh", "-c"]
      args:
        - |
          git config --global --add safe.directory '*'
          cd /tmp && git clone --bare {PROJECT_MOUNT_PATH} repo.git
          apk add --no-cache git-daemon
          git daemon --reuseaddr --base-path=/tmp --export-all /tmp
      ports:
        - containerPort: 9418
      volumeMounts:
        - name: project
          mountPath: {PROJECT_MOUNT_PATH}
          readOnly: true
  volumes:
    - name: project
      hostPath:
        path: {PROJECT_MOUNT_PATH}
        type: Directory
---
apiVersion: v1
kind: Service
metadata:
  name: git-server
  namespace: default
spec:
  selector:
    app: git-server
  ports:
    - port: 9418
      targetPort: 9418
"""
    logger.info("deploying in-cluster git server")
    run(["kubectl", "apply", "-f", "-"], input=manifest)
    _wait_for_pod_ready("git-server", "default", timeout=120)


def _wait_for_pod_ready(name: str, namespace: str, timeout: int = 120) -> None:
    start = time.time()
    while time.time() - start < timeout:
        result = run(
            ["kubectl", "get", "pod", name, "-n", namespace, "-o", "jsonpath={.status.phase}"],
            capture=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip() == "Running":
            return
        time.sleep(3)
    logger.warning("pod %s not ready after %ds", name, timeout)


def setup_argocd_apps(project_dir: Path) -> None:
    """Apply the ArgoCD root Application (app-of-apps) from the project directory.

    The root app points at deploy/argocd/apps in the git source and auto-discovers
    child Applications. The repoURL in the on-disk files must already be correct
    for the target environment (patched for local dev, or rendered with a real
    repo_url for cloud deploy).
    """
    argocd_dir = project_dir / "deploy" / "argocd"
    root_app = argocd_dir / "root-app.yaml"
    if root_app.exists():
        logger.info("applying argocd root application (app-of-apps)")
        run(["kubectl", "apply", "-f", str(root_app)])


def get_argocd_password() -> str:
    """Get the ArgoCD initial admin password."""
    result = run(
        [
            "kubectl",
            "get",
            "secret",
            "argocd-initial-admin-secret",
            "-n",
            "argocd",
            "-o",
            "jsonpath={.data.password}",
        ],
        capture=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return "<not yet available>"
    import base64

    return base64.b64decode(result.stdout.strip()).decode()


def wait_for_argocd_sync(app_names: list[str], timeout: int = 300) -> None:
    """Wait for ArgoCD apps to sync and become healthy."""
    logger.info("waiting for ArgoCD to sync apps")
    start = time.time()
    while time.time() - start < timeout:
        all_healthy = True
        for name in app_names:
            result = run(
                [
                    "kubectl",
                    "get",
                    "application",
                    name,
                    "-n",
                    "argocd",
                    "-o",
                    "jsonpath={.status.health.status}",
                ],
                capture=True,
                check=False,
            )
            if result.returncode != 0 or result.stdout.strip() != "Healthy":
                all_healthy = False
                break
        if all_healthy:
            logger.info("all ArgoCD apps are healthy")
            return
        time.sleep(5)
    logger.warning("ArgoCD apps not all healthy after %ds, continuing anyway", timeout)


def install_helm_releases(project_dir: Path) -> None:
    """Install all helm charts found in deploy/helm/."""
    helm_dir = project_dir / "deploy" / "helm"
    if not helm_dir.is_dir():
        return

    for chart_dir in sorted(helm_dir.iterdir()):
        if not chart_dir.is_dir():
            continue
        logger.info("installing %s helm chart", chart_dir.name)
        run(
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
                "8m",
            ]
        )


def seal_secrets(project_dir: Path) -> None:
    """Seal raw secrets using kubeseal against the running cluster's controller."""
    raw_dir = project_dir / "secrets" / "raw"
    sealed_dir = project_dir / "secrets" / "sealed"
    if not raw_dir.is_dir():
        return

    sealed_dir.mkdir(parents=True, exist_ok=True)

    for raw_file in raw_dir.glob("*.yaml"):
        sealed_file = sealed_dir / raw_file.name
        logger.info("sealing %s", raw_file.name)
        result = run(
            [
                "kubeseal",
                "--format",
                "yaml",
                "--controller-namespace",
                "kube-system",
                "--controller-name",
                "sealed-secrets",
            ],
            input=raw_file.read_text(),
            capture=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            sealed_file.write_text(result.stdout)
            logger.info("sealed secret written to %s", sealed_file)
        else:
            logger.warning(
                "kubeseal failed for %s (exit %d), applying raw secret as fallback",
                raw_file.name,
                result.returncode,
            )
            run(["kubectl", "apply", "-f", str(raw_file)], check=False)


def check_prerequisites() -> list[str]:
    """Check that all required CLI tools are available."""
    errors = []
    for tool in ("docker", "kind", "kubectl", "helm", "kubeseal"):
        if not shutil.which(tool):
            errors.append(f"{tool} is not installed or not on PATH")

    if shutil.which("docker"):
        result = run(["docker", "info"], capture=True, check=False)
        if result.returncode != 0:
            errors.append("Docker daemon is not running (try: systemctl start docker)")

    return errors
