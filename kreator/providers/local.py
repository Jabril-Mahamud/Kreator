import json
import subprocess
import time
from pathlib import Path

import typer

from kreator.core.cluster import (
    CLUSTER_NAME,
    PROJECT_MOUNT_PATH,
    create_cluster,
    delete_cluster,
    get_kubeconfig_context,
    wait_for_nodes_ready,
)
from kreator.core.config import KreatorConfig
from kreator.core.platform import apply_yaml_dir, install_platform
from kreator.core.registry import (
    connect_registry_to_kind,
    create_registry,
    delete_registry,
    get_registry_url,
)
from kreator.providers.base import BaseProvider


class LocalProvider(BaseProvider):
    def __init__(self, config: KreatorConfig, project_dir: Path) -> None:
        super().__init__(config, project_dir)
        self.context = get_kubeconfig_context()
        self.registry_url = get_registry_url()

    def get_context(self) -> str:
        return self.context

    def setup(self) -> None:
        create_registry()
        create_cluster(self.project_dir)
        connect_registry_to_kind(CLUSTER_NAME)
        wait_for_nodes_ready()
        install_platform(self.context)
        self._build_and_push_images()
        self._apply_crossplane_resources()
        self._generate_secrets()
        self._setup_argocd_local_repo()
        self._deploy_with_argocd()

    def destroy(self) -> None:
        delete_cluster()
        delete_registry()

    def _build_and_push_images(self) -> None:
        for app_name in ["backend", "frontend"]:
            app_dir = self.project_dir / "apps" / app_name
            if not app_dir.exists():
                continue
            image = f"{self.registry_url}/{self.config.name}-{app_name}:latest"
            typer.echo(f"Building {app_name} image...")
            subprocess.run(
                ["docker", "build", "-t", image, str(app_dir)],
                check=True,
                capture_output=True,
                text=True,
            )
            typer.echo(f"Pushing {app_name} image...")
            subprocess.run(
                ["docker", "push", image],
                check=True,
                capture_output=True,
                text=True,
            )
            typer.echo(f"{app_name} image pushed to {image}")

    def _apply_crossplane_resources(self) -> None:
        infra = self.project_dir / "infrastructure"
        if not infra.exists():
            return

        typer.echo("Applying Crossplane XRDs...")
        apply_yaml_dir(infra / "xrds", self.context)

        typer.echo("Waiting for XRD to be established...")
        time.sleep(5)

        typer.echo("Applying local compositions...")
        apply_yaml_dir(infra / "compositions" / "local", self.context)

        typer.echo("Applying claims...")
        apply_yaml_dir(infra / "claims", self.context)

    def _generate_secrets(self) -> None:
        typer.echo("Creating application secrets...")
        db_name = self.config.name.replace("-", "_")
        db_url = f"postgresql+asyncpg://postgres:postgres@{self.config.name}-db:5432/{db_name}"

        secret_manifest = f"""\
apiVersion: v1
kind: Secret
metadata:
  name: {self.config.name}-backend-secrets
  namespace: default
type: Opaque
stringData:
  POSTGRES_USER: postgres
  POSTGRES_PASSWORD: postgres
  POSTGRES_DB: {db_name}
  DATABASE_URL: "{db_url}"
"""
        subprocess.run(
            ["kubectl", "--context", self.context, "apply", "-f", "-"],
            input=secret_manifest,
            text=True,
            check=True,
            capture_output=True,
        )
        typer.echo("Secrets created")

    def _setup_argocd_local_repo(self) -> None:
        typer.echo("Configuring ArgoCD for local git repo...")

        result = subprocess.run(
            ["git", "-C", str(self.project_dir), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            typer.echo("Initializing git repo for ArgoCD...")
            subprocess.run(
                ["git", "-C", str(self.project_dir), "init"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(self.project_dir), "add", "-A"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(self.project_dir), "commit", "-m", "initial scaffold"],
                check=True,
                capture_output=True,
                text=True,
            )

        patch = json.dumps(
            {
                "spec": {
                    "template": {
                        "spec": {
                            "volumes": [
                                {
                                    "name": "project-repo",
                                    "hostPath": {"path": PROJECT_MOUNT_PATH, "type": "Directory"},
                                }
                            ],
                            "containers": [
                                {
                                    "name": "argocd-repo-server",
                                    "volumeMounts": [
                                        {
                                            "name": "project-repo",
                                            "mountPath": PROJECT_MOUNT_PATH,
                                            "readOnly": True,
                                        }
                                    ],
                                }
                            ],
                        }
                    }
                }
            }
        )
        subprocess.run(
            [
                "kubectl",
                "--context",
                self.context,
                "patch",
                "deployment",
                "argocd-repo-server",
                "-n",
                "argocd",
                "--type",
                "strategic",
                "-p",
                patch,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        subprocess.run(
            [
                "kubectl",
                "--context",
                self.context,
                "rollout",
                "status",
                "deployment/argocd-repo-server",
                "-n",
                "argocd",
                "--timeout=120s",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        repo_secret = f"""\
apiVersion: v1
kind: Secret
metadata:
  name: local-repo
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
type: Opaque
stringData:
  type: git
  url: file://{PROJECT_MOUNT_PATH}
"""
        subprocess.run(
            ["kubectl", "--context", self.context, "apply", "-f", "-"],
            input=repo_secret,
            text=True,
            check=True,
            capture_output=True,
        )
        typer.echo("ArgoCD local repo configured")

    def _deploy_with_argocd(self) -> None:
        deploy_dir = self.project_dir / "deploy"
        if not deploy_dir.exists():
            return

        typer.echo("Updating ArgoCD app manifests with local repo URL...")
        self._patch_argocd_apps_for_local()

        root_app = deploy_dir / "argocd" / "root-app.yaml"
        if root_app.exists():
            typer.echo("Applying ArgoCD root application...")
            subprocess.run(
                ["kubectl", "--context", self.context, "apply", "-f", str(root_app)],
                check=True,
                capture_output=True,
                text=True,
            )

        for app_yaml in sorted((deploy_dir / "argocd" / "apps").glob("*.yaml")):
            subprocess.run(
                ["kubectl", "--context", self.context, "apply", "-f", str(app_yaml)],
                check=True,
                capture_output=True,
                text=True,
            )

        typer.echo("ArgoCD applications deployed, syncing will begin automatically")

    def _patch_argocd_apps_for_local(self) -> None:
        """Rewrite ArgoCD Application repoURLs to use the local file:// path."""
        argocd_dir = self.project_dir / "deploy" / "argocd"
        local_url = f"file://{PROJECT_MOUNT_PATH}"

        for yaml_file in argocd_dir.rglob("*.yaml"):
            content = yaml_file.read_text()
            if "repoURL:" in content:
                lines = content.split("\n")
                new_lines = []
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("repoURL:"):
                        indent = line[: len(line) - len(line.lstrip())]
                        new_lines.append(f"{indent}repoURL: '{local_url}'")
                    else:
                        new_lines.append(line)
                yaml_file.write_text("\n".join(new_lines))
