from pathlib import Path

from typer.testing import CliRunner

from kreator.main import app

runner = CliRunner()


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
    runner.invoke(
        app,
        [
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
        ],
    )
    kreator_yaml = tmp_path / "test-proj" / "kreator.yaml"
    assert kreator_yaml.exists()
    content = kreator_yaml.read_text()
    assert "test-proj" in content


def test_init_creates_backend(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(
        app,
        [
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
        ],
    )
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
    runner.invoke(
        app,
        [
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
        ],
    )
    frontend = tmp_path / "test-proj" / "apps" / "frontend"
    assert frontend.exists()
    assert (frontend / "package.json").exists()
    assert (frontend / "src" / "app" / "page.tsx").exists()
    assert (frontend / "src" / "app" / "layout.tsx").exists()
    assert (frontend / "src" / "lib" / "api.ts").exists()
    assert (frontend / "Dockerfile").exists()


def test_init_creates_project_files(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(
        app,
        [
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
        ],
    )
    project = tmp_path / "test-proj"
    assert (project / "Makefile").exists()
    assert (project / "README.md").exists()
    assert (project / ".gitignore").exists()


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
