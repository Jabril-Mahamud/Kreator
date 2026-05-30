from pathlib import Path

import pytest

from kreator.core.config import KreatorConfig
from kreator.core.renderer import render_project, render_template_dir


@pytest.fixture
def simple_template(tmp_path: Path) -> Path:
    tpl_dir = tmp_path / "tpl"
    tpl_dir.mkdir()
    (tpl_dir / "hello.txt.j2").write_text("Hello {{ name }}!")
    (tpl_dir / "static.txt").write_text("unchanged")
    sub = tpl_dir / "sub"
    sub.mkdir()
    (sub / "nested.txt.j2").write_text("Project: {{ name }}")
    return tpl_dir


def test_render_template_dir(simple_template: Path, tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    files = render_template_dir(simple_template, output, {"name": "test"})
    assert len(files) == 3
    assert (output / "hello.txt").read_text() == "Hello test!"
    assert (output / "static.txt").read_text() == "unchanged"
    assert (output / "sub" / "nested.txt").read_text() == "Project: test"


def test_render_j2_suffix_stripped(simple_template: Path, tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    render_template_dir(simple_template, output, {"name": "x"})
    assert not (output / "hello.txt.j2").exists()
    assert (output / "hello.txt").exists()


def test_render_project_fastapi(tmp_path: Path) -> None:
    config = KreatorConfig(name="myapp", frontend="nextjs", backend="fastapi")
    output = tmp_path / "myapp"
    files = render_project(config, output)

    assert len(files) > 0
    assert (output / "kreator.yaml").exists()
    assert (output / "Makefile").exists()
    assert (output / "README.md").exists()
    assert (output / ".gitignore").exists()
    assert (output / "apps" / "frontend" / "package.json").exists()
    assert (output / "apps" / "backend" / "pyproject.toml").exists()
    assert (output / "apps" / "backend" / "app" / "main.py").exists()
    assert (output / "infrastructure" / "xrds" / "database.yaml").exists()
    assert (output / "infrastructure" / "claims" / "database.yaml").exists()
    assert (output / "deploy" / "argocd" / "root-app.yaml").exists()
    assert (output / "deploy" / "helm" / "backend" / "Chart.yaml").exists()
    assert (output / "deploy" / "helm" / "frontend" / "Chart.yaml").exists()
    assert (output / "secrets" / "raw" / ".gitkeep").exists()
    assert (output / "secrets" / "sealed" / "secrets.yaml").exists()


def test_render_project_go(tmp_path: Path) -> None:
    config = KreatorConfig(name="myapp", frontend="react", backend="go")
    output = tmp_path / "myapp"
    files = render_project(config, output)

    assert len(files) > 0
    assert (output / "apps" / "backend" / "go.mod").exists()
    assert (output / "apps" / "backend" / "cmd" / "server" / "main.go").exists()
    assert (output / "apps" / "frontend" / "package.json").exists()
    assert (output / "apps" / "frontend" / "src" / "App.tsx").exists()

    go_mod = (output / "apps" / "backend" / "go.mod").read_text()
    assert "myapp-backend" in go_mod


def test_render_project_express(tmp_path: Path) -> None:
    config = KreatorConfig(name="myapp", frontend="nextjs", backend="express")
    output = tmp_path / "myapp"
    files = render_project(config, output)

    assert len(files) > 0
    assert (output / "apps" / "backend" / "package.json").exists()
    assert (output / "apps" / "backend" / "tsconfig.json").exists()
    assert (output / "apps" / "backend" / "src" / "index.ts").exists()

    pkg = (output / "apps" / "backend" / "package.json").read_text()
    assert "myapp-backend" in pkg


def test_render_project_kreator_yaml_content(tmp_path: Path) -> None:
    config = KreatorConfig(name="test-proj", frontend="react", backend="express", region="nyc1")
    output = tmp_path / "test-proj"
    render_project(config, output)

    content = (output / "kreator.yaml").read_text()
    assert "name: test-proj" in content
    assert "frontend: react" in content
    assert "backend: express" in content
    assert "region: nyc1" in content
    assert "repo_url:" in content


def test_render_project_jwt_secret_generated(tmp_path: Path) -> None:
    config = KreatorConfig(name="myapp", backend="fastapi")
    output = tmp_path / "myapp"
    render_project(config, output)

    secrets_path = output / "secrets" / "sealed" / "secrets.yaml"
    content = secrets_path.read_text()
    assert "REPLACE_ME" not in content
    assert "JWT_SECRET:" in content
    assert len(content.split("JWT_SECRET:")[1].strip().strip('"')) > 20


def test_render_project_repo_url_in_argocd(tmp_path: Path) -> None:
    config = KreatorConfig(
        name="myapp",
        backend="fastapi",
        repo_url="https://github.com/me/myapp.git",
    )
    output = tmp_path / "myapp"
    render_project(config, output)

    root_app = (output / "deploy" / "argocd" / "root-app.yaml").read_text()
    assert "https://github.com/me/myapp.git" in root_app
    assert "OWNER" not in root_app


def test_helm_templates_preserve_go_templates(tmp_path: Path) -> None:
    config = KreatorConfig(name="myapp", backend="fastapi")
    output = tmp_path / "myapp"
    render_project(config, output)

    helm_path = output / "deploy" / "helm" / "backend" / "templates" / "deployment.yaml"
    deployment = helm_path.read_text()
    assert "{{ include" in deployment or "{{" in deployment
    assert ".Values.image.repository" in deployment
