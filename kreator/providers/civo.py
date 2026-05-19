import os
import subprocess
import time
from pathlib import Path

import typer

from kreator.core.config import KreatorConfig
from kreator.core.platform import (
    _helm,
    _kubectl,
    _kubectl_apply_stdin,
    _wait_for_deployment,
    apply_yaml_dir,
)
from kreator.providers.base import BaseProvider

CIVO_PROVIDER_VERSION = "v0.4.0"


class CivoProvider(BaseProvider):
    def __init__(self, config: KreatorConfig, project_dir: Path) -> None:
        super().__init__(config, project_dir)
        self.api_key = os.environ.get("CIVO_API_KEY", "")
        self.context = ""

    def get_context(self) -> str:
        return self.context

    def setup(self) -> None:
        if not self.api_key:
            typer.echo(
                "Error: CIVO_API_KEY environment variable is required. "
                "Get your API key from https://dashboard.civo.com/security",
                err=True,
            )
            raise typer.Exit(1)

        typer.echo(f"Deploying '{self.config.name}' to Civo ({self.config.region})...")

        self._provision_cluster()
        self._install_platform()
        self._setup_civo_crossplane_provider()
        self._apply_crossplane_resources()
        self._push_images_to_registry()
        self._deploy_with_argocd()

        typer.echo("")
        typer.echo("Civo deployment complete!")
        typer.echo(f"Cluster: {self.config.name}")
        typer.echo(f"Region: {self.config.region}")
        typer.echo("Run 'kubectl get nodes' to verify the cluster is ready")

    def destroy(self) -> None:
        if not self.api_key:
            self.api_key = os.environ.get("CIVO_API_KEY", "")
        if not self.api_key:
            typer.echo("Error: CIVO_API_KEY required to destroy resources", err=True)
            raise typer.Exit(1)

        typer.echo(f"Destroying Civo resources for '{self.config.name}'...")

        subprocess.run(
            [
                "civo",
                "kubernetes",
                "remove",
                self.config.name,
                "--region",
                self.config.region,
                "-y",
            ],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "CIVO_API_KEY": self.api_key},
        )

        subprocess.run(
            [
                "civo",
                "database",
                "remove",
                f"{self.config.name}-db",
                "--region",
                self.config.region,
                "-y",
            ],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "CIVO_API_KEY": self.api_key},
        )

        typer.echo("Civo resources destroyed")

    def _provision_cluster(self) -> None:
        typer.echo("Provisioning Civo Kubernetes cluster...")
        civo_env = {**os.environ, "CIVO_API_KEY": self.api_key}

        result = subprocess.run(
            [
                "civo",
                "kubernetes",
                "show",
                self.config.name,
                "--region",
                self.config.region,
                "-o",
                "custom",
                "-f",
                "Status",
            ],
            capture_output=True,
            text=True,
            env=civo_env,
        )

        if result.returncode != 0 or "ACTIVE" not in result.stdout:
            subprocess.run(
                [
                    "civo",
                    "kubernetes",
                    "create",
                    self.config.name,
                    "--region",
                    self.config.region,
                    "--nodes",
                    "2",
                    "--size",
                    "g4s.kube.medium",
                    "--wait",
                    "--save",
                    "--merge",
                    "--switch",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=civo_env,
            )
            typer.echo("Cluster provisioned")
        else:
            typer.echo("Cluster already exists")

        result = subprocess.run(
            [
                "civo",
                "kubernetes",
                "show",
                self.config.name,
                "--region",
                self.config.region,
                "-o",
                "custom",
                "-f",
                "KubeConfig",
            ],
            capture_output=True,
            text=True,
            check=True,
            env=civo_env,
        )

        self.context = f"{self.config.name}"
        result = subprocess.run(
            ["kubectl", "config", "current-context"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self.context = result.stdout.strip()

    def _install_platform(self) -> None:
        typer.echo("Installing platform components on Civo cluster...")

        typer.echo("Installing Crossplane...")
        _helm(
            ["repo", "add", "crossplane-stable", "https://charts.crossplane.io/stable"],
            context=self.context,
        )
        _helm(["repo", "update"], context=self.context)
        _kubectl(["create", "namespace", "crossplane-system"], context=self.context)
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
            context=self.context,
        )

        typer.echo("Installing Sealed Secrets...")
        _helm(
            ["repo", "add", "sealed-secrets", "https://bitnami-labs.github.io/sealed-secrets"],
            context=self.context,
        )
        _kubectl(["create", "namespace", "sealed-secrets"], context=self.context)
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
            context=self.context,
        )

        typer.echo("Installing ArgoCD...")
        _kubectl(["create", "namespace", "argocd"], context=self.context)
        _kubectl(
            [
                "apply",
                "-n",
                "argocd",
                "-f",
                "https://raw.githubusercontent.com/argoproj/argo-cd/v2.12.6/manifests/install.yaml",
            ],
            context=self.context,
        )
        _wait_for_deployment("argocd-server", "argocd", self.context, timeout=300)
        typer.echo("Platform installed")

    def _setup_civo_crossplane_provider(self) -> None:
        typer.echo("Installing Crossplane provider-civo...")
        provider_manifest = f"""\
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-civo
spec:
  package: xpkg.upbound.io/civo/provider-civo:{CIVO_PROVIDER_VERSION}
"""
        _kubectl_apply_stdin(provider_manifest, self.context)

        typer.echo("Waiting for provider-civo to become healthy...")
        deadline = time.time() + 180
        while time.time() < deadline:
            result = _kubectl(
                [
                    "get",
                    "provider",
                    "provider-civo",
                    "-o",
                    "jsonpath={.status.conditions[?(@.type=='Healthy')].status}",
                ],
                context=self.context,
            )
            if result.stdout.strip() == "True":
                break
            time.sleep(5)

        secret_manifest = f"""\
apiVersion: v1
kind: Secret
metadata:
  name: civo-credentials
  namespace: crossplane-system
type: Opaque
stringData:
  credentials: '{{"token": "{self.api_key}", "region": "{self.config.region}"}}'
"""
        _kubectl_apply_stdin(secret_manifest, self.context)

        provider_config = """\
apiVersion: civo.crossplane.io/v1alpha1
kind: ProviderConfig
metadata:
  name: default
spec:
  credentials:
    source: Secret
    secretRef:
      name: civo-credentials
      namespace: crossplane-system
      key: credentials
"""
        _kubectl_apply_stdin(provider_config, self.context)
        typer.echo("provider-civo configured")

    def _apply_crossplane_resources(self) -> None:
        infra = self.project_dir / "infrastructure"
        if not infra.exists():
            return

        typer.echo("Applying Crossplane XRDs...")
        apply_yaml_dir(infra / "xrds", self.context)
        time.sleep(5)

        typer.echo("Applying Civo compositions...")
        apply_yaml_dir(infra / "compositions" / "civo", self.context)

        civo_claim = self.project_dir / "infrastructure" / "claims" / "database.yaml"
        if civo_claim.exists():
            content = civo_claim.read_text()
            content = content.replace("provider: local", "provider: civo")
            typer.echo("Applying database claim for Civo...")
            subprocess.run(
                ["kubectl", "--context", self.context, "apply", "-f", "-"],
                input=content,
                text=True,
                check=True,
                capture_output=True,
            )

    def _push_images_to_registry(self) -> None:
        typer.echo("Building and pushing images (requires a container registry)...")
        typer.echo(
            "Note: configure a container registry (e.g. Docker Hub, GHCR) "
            "and update deploy/helm/*/values.yaml with image references"
        )

    def _deploy_with_argocd(self) -> None:
        deploy_dir = self.project_dir / "deploy"
        if not deploy_dir.exists():
            return

        result = subprocess.run(
            ["git", "-C", str(self.project_dir), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            repo_url = result.stdout.strip()
            typer.echo(f"Configuring ArgoCD with repo: {repo_url}")
        else:
            typer.echo("Warning: no git remote found, ArgoCD apps will need manual repo config")
            return

        for yaml_file in sorted(
            (deploy_dir / "argocd").rglob("*.yaml"),
        ):
            content = yaml_file.read_text()
            if "repoURL:" in content and "placeholder" in content:
                content = content.replace(
                    f"https://github.com/placeholder/{self.config.name}.git",
                    repo_url,
                )
                subprocess.run(
                    ["kubectl", "--context", self.context, "apply", "-f", "-"],
                    input=content,
                    text=True,
                    check=True,
                    capture_output=True,
                )
            else:
                subprocess.run(
                    ["kubectl", "--context", self.context, "apply", "-f", str(yaml_file)],
                    check=True,
                    capture_output=True,
                    text=True,
                )

        typer.echo("ArgoCD applications deployed")
