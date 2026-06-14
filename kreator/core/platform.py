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
            '{"data": {"server.insecure": "true"}}',
        ],
        check=False,
    )

    try:
        _wait_for_deployment("argocd-server", "argocd", timeout=300)
    except RuntimeError:
        logger.warning("argocd-server not ready yet, it will become available in the background")

    _set_argocd_admin_password()

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
    - host: argocd.localhost
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: argocd-server
                port:
                  number: 80
"""
    run(["kubectl", "apply", "-f", "-"], input=ingress_yaml)


ARGOCD_ADMIN_PASSWORD = "admin123"


def _set_argocd_admin_password() -> None:
    """Set the ArgoCD admin password to a known value."""
    _set_argocd_account_password("admin", ARGOCD_ADMIN_PASSWORD)


def _set_argocd_account_password(key_prefix: str, password: str) -> None:
    """Patch a bcrypt password into argocd-secret under the given key prefix.

    Use "admin" for the built-in admin, "accounts.<name>" for local users.
    """
    import base64

    import bcrypt

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode()
    encoded = base64.b64encode(hashed.encode()).decode()
    mtime = base64.b64encode(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()).encode()).decode()

    run(
        [
            "kubectl",
            "patch",
            "secret",
            "argocd-secret",
            "-n",
            "argocd",
            "-p",
            f'{{"data": {{"{key_prefix}.password": "{encoded}",'
            f' "{key_prefix}.passwordMtime": "{mtime}"}}}}',
        ],
        check=False,
    )


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


def wait_for_db_ready(name: str, namespace: str = "default", timeout: int = 180) -> None:
    """Wait for the Crossplane-managed database StatefulSet to have a ready pod."""
    sts_name = f"{name}-db"
    logger.info("waiting for database to be ready (%s)", sts_name)
    start = time.time()
    while time.time() - start < timeout:
        result = run(
            [
                "kubectl",
                "get",
                "statefulset",
                sts_name,
                "-n",
                namespace,
                "-o",
                "jsonpath={.status.readyReplicas}",
            ],
            capture=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip() == "1":
            logger.info("database is ready")
            return
        time.sleep(5)
    logger.warning("database not ready after %ds, continuing anyway", timeout)


GIT_SERVER_URL = "git://git-server.default.svc/repo.git"

# Local dev commits land on this dedicated branch instead of the user's branch,
# so `kreator dev` never pollutes their working branch (see ISSUES.md #4). The
# git server serves this branch as HEAD, which is what ArgoCD tracks.
DEV_BRANCH = "kreator-local-dev"


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
          if git --git-dir=repo.git show-ref --verify --quiet refs/heads/{DEV_BRANCH}; then
            git --git-dir=repo.git symbolic-ref HEAD refs/heads/{DEV_BRANCH}
          fi
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
    # The git server bare-clones the project at pod startup, so on re-runs we
    # must recreate the pod to pick up new commits; otherwise ArgoCD keeps
    # serving the snapshot from the first run and code changes never deploy.
    run(
        ["kubectl", "delete", "pod", "git-server", "-n", "default", "--ignore-not-found"],
        check=False,
    )
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


def create_argocd_project_user(project_name: str) -> None:
    """Create a project-scoped ArgoCD local user that only sees this project's apps.

    The user is named after the project and shares the known dev password.
    Logging in as it filters the dashboard to this project; admin still sees all.
    """
    import json

    logger.info("creating project-scoped argocd user: %s", project_name)

    run(
        [
            "kubectl",
            "patch",
            "configmap",
            "argocd-cm",
            "-n",
            "argocd",
            "-p",
            json.dumps({"data": {f"accounts.{project_name}": "login"}}),
        ],
        check=False,
    )

    rules = [
        f"p, {project_name}, applications, *, {project_name}/*, allow",
        f"p, {project_name}, projects, get, {project_name}, allow",
        f"p, {project_name}, logs, get, {project_name}/*, allow",
        f"p, {project_name}, exec, create, {project_name}/*, allow",
    ]
    result = run(
        [
            "kubectl",
            "get",
            "configmap",
            "argocd-rbac-cm",
            "-n",
            "argocd",
            "-o",
            "jsonpath={.data.policy\\.csv}",
        ],
        capture=True,
        check=False,
    )
    existing = result.stdout.strip().splitlines() if result.returncode == 0 else []
    policy = existing + [r for r in rules if r not in existing]
    run(
        [
            "kubectl",
            "patch",
            "configmap",
            "argocd-rbac-cm",
            "-n",
            "argocd",
            "-p",
            json.dumps({"data": {"policy.csv": "\n".join(policy) + "\n"}}),
        ],
        check=False,
    )

    _set_argocd_account_password(f"accounts.{project_name}", ARGOCD_ADMIN_PASSWORD)

    run(
        ["kubectl", "rollout", "restart", "deployment/argocd-server", "-n", "argocd"],
        check=False,
    )


def setup_argocd_apps(project_dir: Path, project_name: str) -> None:
    """Create the ArgoCD AppProject and apply the root Application (app-of-apps).

    Creates the target namespace if it does not exist, then applies the
    AppProject so ArgoCD knows about the project before the root app
    tries to reference it.
    """
    run(["kubectl", "create", "namespace", project_name], check=False)
    create_argocd_project_user(project_name)

    argocd_dir = project_dir / "deploy" / "argocd"

    appproject = argocd_dir / "appproject.yaml"
    if appproject.exists():
        logger.info("applying argocd appproject for %s", project_name)
        run(["kubectl", "apply", "-f", str(appproject)])

    root_app = argocd_dir / "root-app.yaml"
    if root_app.exists():
        logger.info("applying argocd root application (app-of-apps)")
        run(["kubectl", "apply", "-f", str(root_app)])


def hard_refresh_apps(project_name: str) -> None:
    """Force ArgoCD to re-pull from git for every application in a project.

    Annotating an Application with a hard refresh makes ArgoCD drop its cached
    manifests and re-read the git repo, so new commits served by the recreated
    git server are picked up without a full `kreator dev` re-run (ISSUES.md #3).
    """
    result = run(
        [
            "kubectl",
            "get",
            "applications",
            "-n",
            "argocd",
            "-o",
            'jsonpath={range .items[?(@.spec.project=="'
            + project_name
            + '")]}{.metadata.name}{"\\n"}{end}',
        ],
        capture=True,
        check=False,
    )
    names = [n for n in result.stdout.split() if n]
    if not names:
        logger.warning("no argocd applications found for project %s", project_name)
        return
    for name in names:
        run(
            [
                "kubectl",
                "annotate",
                "application",
                name,
                "-n",
                "argocd",
                "argocd.argoproj.io/refresh=hard",
                "--overwrite",
            ],
            check=False,
        )
        logger.info("hard-refreshed argocd app %s", name)


def get_argocd_password() -> str:
    """Get the ArgoCD admin password."""
    return ARGOCD_ADMIN_PASSWORD


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
            run(["kubectl", "apply", "-f", str(sealed_file)], check=False)
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
