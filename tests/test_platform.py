from pathlib import Path

import yaml

from kreator.core.config import KreatorConfig
from kreator.core.platform import patch_argocd_repo_url, patch_claims_for_env


def _write_claim(path: Path, provider: str) -> None:
    claim = {
        "apiVersion": "kreator.dev/v1alpha1",
        "kind": "Database",
        "metadata": {"name": "demo-db", "namespace": "default"},
        "spec": {
            "parameters": {"name": "demo-db", "namespace": "default", "size": "small"},
            "compositionSelector": {"matchLabels": {"provider": provider}},
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(claim, default_flow_style=False))


def _write_argocd_app(path: Path, repo_url: str) -> None:
    app = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {"name": "demo-backend", "namespace": "argocd"},
        "spec": {
            "project": "default",
            "source": {
                "repoURL": repo_url,
                "targetRevision": "HEAD",
                "path": "deploy/helm/backend",
            },
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": "default",
            },
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(app, default_flow_style=False))


def test_patch_claims_for_env_civo_to_local(tmp_path: Path) -> None:
    claim_path = tmp_path / "infrastructure" / "claims" / "database.yaml"
    _write_claim(claim_path, "civo")

    patch_claims_for_env(tmp_path, "local")

    doc = yaml.safe_load(claim_path.read_text())
    assert doc["spec"]["compositionSelector"]["matchLabels"]["provider"] == "local"


def test_patch_claims_for_env_local_to_civo(tmp_path: Path) -> None:
    claim_path = tmp_path / "infrastructure" / "claims" / "database.yaml"
    _write_claim(claim_path, "local")

    patch_claims_for_env(tmp_path, "civo")

    doc = yaml.safe_load(claim_path.read_text())
    assert doc["spec"]["compositionSelector"]["matchLabels"]["provider"] == "civo"


def test_patch_claims_for_env_noop_when_already_correct(tmp_path: Path) -> None:
    claim_path = tmp_path / "infrastructure" / "claims" / "database.yaml"
    _write_claim(claim_path, "local")

    patch_claims_for_env(tmp_path, "local")

    doc = yaml.safe_load(claim_path.read_text())
    assert doc["spec"]["compositionSelector"]["matchLabels"]["provider"] == "local"


def test_patch_claims_for_env_missing_dir(tmp_path: Path) -> None:
    patch_claims_for_env(tmp_path, "local")


def test_patch_argocd_repo_url(tmp_path: Path) -> None:
    original_url = "https://github.com/OWNER/demo.git"
    git_server_url = "git://git-server.default.svc/repo.git"

    app_path = tmp_path / "deploy" / "argocd" / "apps" / "backend.yaml"
    _write_argocd_app(app_path, original_url)
    root_path = tmp_path / "deploy" / "argocd" / "root-app.yaml"
    _write_argocd_app(root_path, original_url)

    patch_argocd_repo_url(tmp_path, git_server_url)

    doc = yaml.safe_load(app_path.read_text())
    assert doc["spec"]["source"]["repoURL"] == git_server_url

    root = yaml.safe_load(root_path.read_text())
    assert root["spec"]["source"]["repoURL"] == git_server_url


def test_patch_argocd_repo_url_missing_dir(tmp_path: Path) -> None:
    patch_argocd_repo_url(tmp_path, "git://git-server.default.svc/repo.git")


def test_deploy_rejects_placeholder_repo_url() -> None:
    config = KreatorConfig(
        name="demo",
        frontend="nextjs",
        backend="fastapi",
        provider="civo",
    )
    repo_url = config.repo_url or ""
    if not repo_url:
        repo_url = f"https://github.com/OWNER/{config.name}.git"
    assert "OWNER" in repo_url, "default repo_url should contain the OWNER placeholder"


def test_deploy_accepts_real_repo_url() -> None:
    config = KreatorConfig(
        name="demo",
        frontend="nextjs",
        backend="fastapi",
        provider="civo",
        repo_url="https://github.com/myuser/demo.git",
    )
    repo_url = config.repo_url or ""
    assert "OWNER" not in repo_url
