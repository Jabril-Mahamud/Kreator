from pathlib import Path

from typer.testing import CliRunner

from kreator.main import app

runner = CliRunner()

INIT_ARGS = [
    "init",
    "test-proj",
    "--frontend",
    "nextjs",
    "--backend",
    "fastapi",
    "--provider",
    "civo",
    "--region",
    "lon1",
]


def test_init_creates_project(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "init",
            "my-app",
            "--frontend",
            "nextjs",
            "--backend",
            "fastapi",
            "--provider",
            "civo",
            "--region",
            "lon1",
        ],
    )
    assert result.exit_code == 0, result.output
    project = tmp_path / "my-app"
    assert project.exists()


def test_init_creates_kreator_yaml(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, INIT_ARGS)
    kreator_yaml = tmp_path / "test-proj" / "kreator.yaml"
    assert kreator_yaml.exists()
    content = kreator_yaml.read_text()
    assert "test-proj" in content


def test_init_creates_backend(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, INIT_ARGS)
    backend = tmp_path / "test-proj" / "apps" / "backend"
    assert backend.exists()
    assert (backend / "app" / "main.py").exists()
    assert (backend / "app" / "config.py").exists()
    assert (backend / "app" / "models.py").exists()
    assert (backend / "app" / "routes" / "health.py").exists()
    assert (backend / "app" / "routes" / "items.py").exists()
    assert (backend / "pyproject.toml").exists()
    assert (backend / "Dockerfile").exists()
    assert (backend / "alembic.ini").exists()
    assert (backend / "alembic" / "env.py").exists()


def test_init_creates_frontend(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, INIT_ARGS)
    frontend = tmp_path / "test-proj" / "apps" / "frontend"
    assert frontend.exists()
    assert (frontend / "package.json").exists()
    assert (frontend / "src" / "app" / "page.tsx").exists()
    assert (frontend / "src" / "app" / "layout.tsx").exists()
    assert (frontend / "src" / "lib" / "api.ts").exists()
    assert (frontend / "Dockerfile").exists()


def test_init_creates_project_files(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, INIT_ARGS)
    project = tmp_path / "test-proj"
    assert (project / "Makefile").exists()
    assert (project / "README.md").exists()
    assert (project / ".gitignore").exists()


def test_init_creates_infrastructure(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, INIT_ARGS)
    infra = tmp_path / "test-proj" / "infrastructure"
    assert (infra / "xrds" / "database.yaml").exists()
    assert (infra / "compositions" / "local" / "database.yaml").exists()
    assert (infra / "claims" / "database.yaml").exists()
    assert (infra / "provider-configs" / "local.yaml").exists()


def test_init_creates_deploy(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, INIT_ARGS)
    deploy = tmp_path / "test-proj" / "deploy"
    assert (deploy / "argocd" / "root-app.yaml").exists()
    assert (deploy / "argocd" / "apps" / "frontend.yaml").exists()
    assert (deploy / "argocd" / "apps" / "backend.yaml").exists()
    assert (deploy / "argocd" / "apps" / "database.yaml").exists()
    assert (deploy / "helm" / "backend" / "Chart.yaml").exists()
    assert (deploy / "helm" / "backend" / "values.yaml").exists()
    assert (deploy / "helm" / "backend" / "templates" / "deployment.yaml").exists()
    assert (deploy / "helm" / "frontend" / "Chart.yaml").exists()
    assert (deploy / "helm" / "frontend" / "values.yaml").exists()


def test_init_creates_secrets_dirs(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, INIT_ARGS)
    secrets = tmp_path / "test-proj" / "secrets"
    assert (secrets / "raw").is_dir()
    assert (secrets / "sealed").is_dir()


def test_init_renders_project_name_in_templates(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(
        app,
        [
            "init",
            "cool-app",
            "--frontend",
            "nextjs",
            "--backend",
            "fastapi",
            "--provider",
            "civo",
            "--region",
            "lon1",
        ],
    )
    package_json = (tmp_path / "cool-app" / "apps" / "frontend" / "package.json").read_text()
    assert "cool-app-frontend" in package_json

    pyproject = (tmp_path / "cool-app" / "apps" / "backend" / "pyproject.toml").read_text()
    assert "cool-app-backend" in pyproject

    helm_chart = (tmp_path / "cool-app" / "deploy" / "helm" / "backend" / "Chart.yaml").read_text()
    assert "cool-app-backend" in helm_chart


def test_init_rejects_existing_directory(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "existing").mkdir()
    result = runner.invoke(
        app,
        [
            "init",
            "existing",
            "--frontend",
            "nextjs",
            "--backend",
            "fastapi",
            "--provider",
            "civo",
            "--region",
            "lon1",
        ],
    )
    assert result.exit_code == 1


def test_init_rejects_invalid_name(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "init",
            "Bad_Name",
            "--frontend",
            "nextjs",
            "--backend",
            "fastapi",
            "--provider",
            "civo",
            "--region",
            "lon1",
        ],
    )
    assert result.exit_code == 1


def test_init_react_express(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "init",
            "alt-app",
            "--frontend",
            "react",
            "--backend",
            "express",
            "--provider",
            "civo",
            "--region",
            "lon1",
        ],
    )
    assert result.exit_code == 0, result.output
    project = tmp_path / "alt-app"
    assert (project / "apps" / "frontend" / "package.json").exists()
    assert (project / "apps" / "frontend" / "vite.config.ts").exists()
    assert (project / "apps" / "frontend" / "src" / "App.tsx").exists()
    assert (project / "apps" / "backend" / "package.json").exists()
    assert (project / "apps" / "backend" / "src" / "index.ts").exists()
    assert (project / "apps" / "backend" / "Dockerfile").exists()
    assert (project / "deploy" / "helm" / "backend" / "Chart.yaml").exists()
    assert (project / "infrastructure" / "xrds" / "database.yaml").exists()

    pkg = (project / "apps" / "frontend" / "package.json").read_text()
    assert "alt-app-frontend" in pkg
    backend_pkg = (project / "apps" / "backend" / "package.json").read_text()
    assert "alt-app-backend" in backend_pkg
