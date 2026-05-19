import subprocess
import time
from pathlib import Path

import typer


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def _kubectl(args: list[str], context: str) -> subprocess.CompletedProcess:
    return _run(["kubectl", "--context", context] + args)


def _kubectl_apply_stdin(manifest: str, context: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["kubectl", "--context", context, "apply", "-f", "-"],
        input=manifest,
        text=True,
        check=True,
        capture_output=True,
    )


def _helm(args: list[str], context: str) -> subprocess.CompletedProcess:
    return _run(["helm", "--kube-context", context] + args)


def _wait_for_deployment(name: str, namespace: str, context: str, timeout: int = 300) -> None:
    _kubectl(
        ["rollout", "status", f"deployment/{name}", "-n", namespace, f"--timeout={timeout}s"],
        context=context,
    )


def install_crossplane(context: str) -> None:
    typer.echo("Installing Crossplane...")
    _helm(
        ["repo", "add", "crossplane-stable", "https://charts.crossplane.io/stable"],
        context=context,
    )
    _helm(["repo", "update"], context=context)

    _kubectl(["create", "namespace", "crossplane-system"], context=context)

    _helm(
        [
            "upgrade",
            "--install",
            "crossplane",
            "crossplane-stable/crossplane",
            "--namespace",
            "crossplane-system",
            "--wait",
            "--timeout",
            "5m",
        ],
        context=context,
    )
    typer.echo("Crossplane installed")


def install_crossplane_provider_kubernetes(context: str) -> None:
    typer.echo("Installing Crossplane provider-kubernetes...")
    manifest = """\
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-kubernetes
spec:
  package: xpkg.upbound.io/crossplane-contrib/provider-kubernetes:v0.14.1
"""
    _kubectl_apply_stdin(manifest, context)

    typer.echo("Waiting for provider-kubernetes to become healthy...")
    deadline = time.time() + 180
    while time.time() < deadline:
        result = _kubectl(
            [
                "get",
                "provider",
                "provider-kubernetes",
                "-o",
                "jsonpath={.status.conditions[?(@.type=='Healthy')].status}",
            ],
            context=context,
        )
        if result.stdout.strip() == "True":
            break
        time.sleep(5)

    sa_binding = """\
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: provider-kubernetes-admin
subjects:
  - kind: ServiceAccount
    name: provider-kubernetes-*
    namespace: crossplane-system
roleRef:
  kind: ClusterRole
  name: cluster-admin
  apiGroup: rbac.authorization.k8s.io
"""
    _kubectl_apply_stdin(sa_binding, context)

    provider_config = """\
apiVersion: kubernetes.crossplane.io/v1alpha1
kind: ProviderConfig
metadata:
  name: default
spec:
  credentials:
    source: InjectedIdentity
"""
    _kubectl_apply_stdin(provider_config, context)
    typer.echo("provider-kubernetes configured")


def install_argocd(context: str) -> None:
    typer.echo("Installing ArgoCD...")
    _kubectl(["create", "namespace", "argocd"], context=context)
    _kubectl(
        [
            "apply",
            "-n",
            "argocd",
            "-f",
            "https://raw.githubusercontent.com/argoproj/argo-cd/v2.12.6/manifests/install.yaml",
        ],
        context=context,
    )
    typer.echo("Waiting for ArgoCD server...")
    _wait_for_deployment("argocd-server", "argocd", context, timeout=300)

    _kubectl(
        [
            "patch",
            "deployment",
            "argocd-server",
            "-n",
            "argocd",
            "--type",
            "json",
            "-p",
            '[{"op":"add","path":"/spec/template/spec/containers/0/command",'
            '"value":["argocd-server","--insecure"]}]',
        ],
        context=context,
    )

    _kubectl(
        [
            "rollout",
            "status",
            "deployment/argocd-server",
            "-n",
            "argocd",
            "--timeout=120s",
        ],
        context=context,
    )
    typer.echo("ArgoCD installed")


def install_ingress_nginx(context: str) -> None:
    typer.echo("Installing ingress-nginx...")
    _kubectl(
        [
            "apply",
            "-f",
            "https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.3"
            "/deploy/static/provider/kind/deploy.yaml",
        ],
        context=context,
    )
    typer.echo("Waiting for ingress-nginx...")
    deadline = time.time() + 180
    while time.time() < deadline:
        result = _kubectl(
            [
                "get",
                "pods",
                "-n",
                "ingress-nginx",
                "-l",
                "app.kubernetes.io/component=controller",
                "-o",
                "jsonpath={.items[0].status.phase}",
            ],
            context=context,
        )
        if result.stdout.strip() == "Running":
            break
        time.sleep(5)
    typer.echo("ingress-nginx installed")


def install_sealed_secrets(context: str) -> None:
    typer.echo("Installing Sealed Secrets...")
    _helm(
        ["repo", "add", "sealed-secrets", "https://bitnami-labs.github.io/sealed-secrets"],
        context=context,
    )
    _helm(["repo", "update"], context=context)
    _kubectl(["create", "namespace", "sealed-secrets"], context=context)
    _helm(
        [
            "upgrade",
            "--install",
            "sealed-secrets",
            "sealed-secrets/sealed-secrets",
            "--namespace",
            "sealed-secrets",
            "--wait",
            "--timeout",
            "3m",
        ],
        context=context,
    )
    typer.echo("Sealed Secrets installed")


def apply_yaml_dir(directory: Path, context: str, namespace: str | None = None) -> None:
    if not directory.exists():
        return
    ns_args = ["-n", namespace] if namespace else []
    for yaml_file in sorted(directory.glob("*.yaml")):
        _kubectl(["apply", "-f", str(yaml_file)] + ns_args, context=context)


def install_observability(context: str, project_dir: Path) -> None:
    obs_dir = project_dir / "deploy" / "observability"
    if not obs_dir.exists():
        typer.echo("No observability templates found, skipping")
        return

    typer.echo("Installing observability stack (LGTM)...")
    _kubectl(["create", "namespace", "observability"], context=context)

    _helm(["repo", "add", "grafana", "https://grafana.github.io/helm-charts"], context=context)
    _helm(["repo", "update"], context=context)

    loki_values = obs_dir / "loki-values.yaml"
    if loki_values.exists():
        typer.echo("Installing Loki...")
        _helm(
            [
                "upgrade",
                "--install",
                "loki",
                "grafana/loki",
                "--namespace",
                "observability",
                "-f",
                str(loki_values),
                "--wait",
                "--timeout",
                "5m",
            ],
            context=context,
        )

    tempo_values = obs_dir / "tempo-values.yaml"
    if tempo_values.exists():
        typer.echo("Installing Tempo...")
        _helm(
            [
                "upgrade",
                "--install",
                "tempo",
                "grafana/tempo",
                "--namespace",
                "observability",
                "-f",
                str(tempo_values),
                "--wait",
                "--timeout",
                "3m",
            ],
            context=context,
        )

    mimir_values = obs_dir / "mimir-values.yaml"
    if mimir_values.exists():
        typer.echo("Installing Mimir...")
        _helm(
            [
                "upgrade",
                "--install",
                "mimir",
                "grafana/mimir-distributed",
                "--namespace",
                "observability",
                "-f",
                str(mimir_values),
                "--wait",
                "--timeout",
                "5m",
            ],
            context=context,
        )

    promtail_values = obs_dir / "promtail-values.yaml"
    if promtail_values.exists():
        typer.echo("Installing Promtail...")
        _helm(
            [
                "upgrade",
                "--install",
                "promtail",
                "grafana/promtail",
                "--namespace",
                "observability",
                "-f",
                str(promtail_values),
                "--wait",
                "--timeout",
                "3m",
            ],
            context=context,
        )

    dashboard_file = obs_dir / "dashboards" / "app.json"
    if dashboard_file.exists():
        cm_name = "grafana-dashboards"
        result = _kubectl(
            ["get", "configmap", cm_name, "-n", "observability"],
            context=context,
        )
        if result.returncode != 0:
            _kubectl(
                [
                    "create",
                    "configmap",
                    cm_name,
                    "-n",
                    "observability",
                    f"--from-file=app.json={dashboard_file}",
                ],
                context=context,
            )

    grafana_values = obs_dir / "grafana-values.yaml"
    if grafana_values.exists():
        typer.echo("Installing Grafana...")
        _helm(
            [
                "upgrade",
                "--install",
                "grafana",
                "grafana/grafana",
                "--namespace",
                "observability",
                "-f",
                str(grafana_values),
                "--wait",
                "--timeout",
                "3m",
            ],
            context=context,
        )

    typer.echo("Observability stack installed")
    typer.echo("  Grafana: http://grafana.localhost (admin/admin)")


def install_platform(context: str) -> None:
    install_ingress_nginx(context)
    install_crossplane(context)
    install_crossplane_provider_kubernetes(context)
    install_sealed_secrets(context)
    install_argocd(context)
