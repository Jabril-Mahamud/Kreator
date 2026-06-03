from pathlib import Path

import pytest
from typer.testing import CliRunner

from kreator.main import app

runner = CliRunner()


@pytest.fixture
def run_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_init_default(run_in_tmp: Path) -> None:
    result = runner.invoke(app, ["init", "my-app"])
    assert result.exit_code == 0
    assert "Created project 'my-app'" in result.output
    assert (run_in_tmp / "my-app" / "kreator.yaml").exists()
    assert (run_in_tmp / "my-app" / "apps" / "frontend").exists()
    assert (run_in_tmp / "my-app" / "apps" / "backend").exists()
    assert (run_in_tmp / "my-app" / ".git").is_dir()


def test_init_fastapi(run_in_tmp: Path) -> None:
    result = runner.invoke(app, ["init", "my-app", "--backend", "fastapi"])
    assert result.exit_code == 0
    assert (run_in_tmp / "my-app" / "apps" / "backend" / "pyproject.toml").exists()
    assert (run_in_tmp / "my-app" / "apps" / "backend" / "app" / "main.py").exists()


def test_init_go(run_in_tmp: Path) -> None:
    result = runner.invoke(app, ["init", "my-app", "--backend", "go"])
    assert result.exit_code == 0
    assert (run_in_tmp / "my-app" / "apps" / "backend" / "go.mod").exists()
    assert (run_in_tmp / "my-app" / "apps" / "backend" / "cmd" / "server" / "main.go").exists()


def test_init_express(run_in_tmp: Path) -> None:
    result = runner.invoke(app, ["init", "my-app", "--backend", "express"])
    assert result.exit_code == 0
    assert (run_in_tmp / "my-app" / "apps" / "backend" / "package.json").exists()
    assert (run_in_tmp / "my-app" / "apps" / "backend" / "src" / "index.ts").exists()


def test_init_react_frontend(run_in_tmp: Path) -> None:
    result = runner.invoke(app, ["init", "my-app", "--frontend", "react"])
    assert result.exit_code == 0
    assert (run_in_tmp / "my-app" / "apps" / "frontend" / "src" / "App.tsx").exists()
    assert (run_in_tmp / "my-app" / "apps" / "frontend" / "vite.config.ts").exists()


def test_init_nextjs_frontend(run_in_tmp: Path) -> None:
    result = runner.invoke(app, ["init", "my-app", "--frontend", "nextjs"])
    assert result.exit_code == 0
    assert (run_in_tmp / "my-app" / "apps" / "frontend" / "next.config.js").exists()
    assert (run_in_tmp / "my-app" / "apps" / "frontend" / "src" / "app" / "page.tsx").exists()


def test_init_invalid_backend(run_in_tmp: Path) -> None:
    result = runner.invoke(app, ["init", "my-app", "--backend", "django"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_init_invalid_frontend(run_in_tmp: Path) -> None:
    result = runner.invoke(app, ["init", "my-app", "--frontend", "svelte"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_init_existing_directory(run_in_tmp: Path) -> None:
    (run_in_tmp / "my-app").mkdir()
    result = runner.invoke(app, ["init", "my-app"])
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_init_infrastructure_generated(run_in_tmp: Path) -> None:
    result = runner.invoke(app, ["init", "my-app"])
    assert result.exit_code == 0
    base = run_in_tmp / "my-app"
    assert (base / "infrastructure" / "xrds" / "database.yaml").exists()
    assert (base / "infrastructure" / "compositions" / "local" / "database.yaml").exists()
    assert (base / "infrastructure" / "compositions" / "civo" / "database.yaml").exists()
    assert (base / "infrastructure" / "claims" / "database.yaml").exists()
    assert (base / "deploy" / "argocd" / "root-app.yaml").exists()
    assert (base / "deploy" / "argocd" / "apps" / "frontend.yaml").exists()
    assert (base / "deploy" / "argocd" / "apps" / "backend.yaml").exists()
    assert (base / "deploy" / "helm" / "backend" / "Chart.yaml").exists()
    assert (base / "deploy" / "helm" / "frontend" / "Chart.yaml").exists()
    assert (base / "secrets" / "sealed" / "secrets.yaml").exists()
    assert (base / "secrets" / "raw" / ".gitkeep").exists()


def test_init_all_combinations(run_in_tmp: Path) -> None:
    """Verify every frontend x backend combination renders without error."""
    combos = [
        ("nextjs", "fastapi"),
        ("nextjs", "go"),
        ("nextjs", "express"),
        ("react", "fastapi"),
        ("react", "go"),
        ("react", "express"),
        ("expo", "fastapi"),
        ("expo", "go"),
        ("expo", "express"),
    ]
    for frontend, backend in combos:
        name = f"app-{frontend}-{backend}"
        result = runner.invoke(app, ["init", name, "--frontend", frontend, "--backend", backend])
        assert result.exit_code == 0, f"Failed for {frontend}/{backend}: {result.output}"
        assert (run_in_tmp / name / "kreator.yaml").exists()


def test_init_multi_frontend(run_in_tmp: Path) -> None:
    result = runner.invoke(
        app, ["init", "my-app", "--frontend", "web:nextjs", "--frontend", "mobile:expo"]
    )
    assert result.exit_code == 0
    base = run_in_tmp / "my-app"

    assert (base / "apps" / "web").exists()
    assert (base / "apps" / "mobile").exists()
    assert not (base / "apps" / "frontend").exists()

    assert (base / "deploy" / "helm" / "web" / "Chart.yaml").exists()
    assert not (base / "deploy" / "helm" / "mobile").exists()

    assert (base / "deploy" / "argocd" / "apps" / "web.yaml").exists()
    assert not (base / "deploy" / "argocd" / "apps" / "mobile.yaml").exists()

    assert (base / ".github" / "workflows" / "mobile-mobile.yml").exists()

    assert "web (nextjs, web)" in result.output
    assert "mobile (expo, mobile)" in result.output


def test_init_multi_frontend_two_web(run_in_tmp: Path) -> None:
    result = runner.invoke(
        app, ["init", "my-app", "--frontend", "web:nextjs", "--frontend", "admin:react"]
    )
    assert result.exit_code == 0
    base = run_in_tmp / "my-app"

    assert (base / "apps" / "web").exists()
    assert (base / "apps" / "admin").exists()
    assert (base / "deploy" / "helm" / "web" / "Chart.yaml").exists()
    assert (base / "deploy" / "helm" / "admin" / "Chart.yaml").exists()
    assert (base / "deploy" / "argocd" / "apps" / "web.yaml").exists()
    assert (base / "deploy" / "argocd" / "apps" / "admin.yaml").exists()


def test_init_expo_frontend(run_in_tmp: Path) -> None:
    result = runner.invoke(app, ["init", "my-app", "--frontend", "expo"])
    assert result.exit_code == 0
    base = run_in_tmp / "my-app"

    assert (base / "apps" / "frontend" / "package.json").exists()
    assert (base / "apps" / "frontend" / "app.json").exists()
    assert (base / "apps" / "frontend" / "eas.json").exists()
    assert (base / "apps" / "frontend" / "src" / "app" / "_layout.tsx").exists()

    assert not (base / "deploy" / "helm" / "frontend").exists()
