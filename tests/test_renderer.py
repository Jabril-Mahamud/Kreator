from pathlib import Path

import pytest

from kreator.core.config import FrontendSpec, KreatorConfig
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


def test_render_template_dir_dynamic_filename(tmp_path: Path) -> None:
    tpl_dir = tmp_path / "tpl"
    tpl_dir.mkdir()
    (tpl_dir / "{{ app_name }}.txt.j2").write_text("content for {{ app_name }}")
    output = tmp_path / "out"
    output.mkdir()
    files = render_template_dir(tpl_dir, output, {"app_name": "mobile"})
    assert len(files) == 1
    assert (output / "mobile.txt").exists()
    assert (output / "mobile.txt").read_text() == "content for mobile"


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
    assert (output / "secrets" / "raw" / "jwt-secret.yaml").exists()


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

    raw_path = output / "secrets" / "raw" / "jwt-secret.yaml"
    content = raw_path.read_text()
    assert "REPLACE_ME" not in content
    assert "JWT_SECRET:" in content
    assert len(content.split("JWT_SECRET:")[1].strip().strip('"')) > 20
    assert not (output / "secrets" / "sealed" / "secrets.yaml").exists()


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


def test_render_project_multi_frontend(tmp_path: Path) -> None:
    config = KreatorConfig(
        name="myapp",
        frontend=None,
        frontends=[
            FrontendSpec(name="web", template="nextjs"),
            FrontendSpec(name="mobile", template="expo"),
        ],
        backend="fastapi",
    )
    output = tmp_path / "myapp"
    files = render_project(config, output)

    assert len(files) > 0

    assert (output / "apps" / "web" / "package.json").exists()
    assert (output / "apps" / "web" / "next.config.js").exists()

    assert (output / "apps" / "mobile" / "package.json").exists()
    assert (output / "apps" / "mobile" / "app.json").exists()
    assert (output / "apps" / "mobile" / "eas.json").exists()

    assert (output / "deploy" / "helm" / "web" / "Chart.yaml").exists()
    web_chart = (output / "deploy" / "helm" / "web" / "Chart.yaml").read_text()
    assert "myapp-web" in web_chart

    assert not (output / "deploy" / "helm" / "mobile").exists()

    assert (output / "deploy" / "argocd" / "apps" / "web.yaml").exists()
    web_argocd = (output / "deploy" / "argocd" / "apps" / "web.yaml").read_text()
    assert "myapp-web" in web_argocd
    assert "deploy/helm/web" in web_argocd

    assert not (output / "deploy" / "argocd" / "apps" / "mobile.yaml").exists()

    assert (output / ".github" / "workflows" / "mobile-mobile.yml").exists()


def test_render_project_multi_frontend_kreator_yaml(tmp_path: Path) -> None:
    config = KreatorConfig(
        name="myapp",
        frontend=None,
        frontends=[
            FrontendSpec(name="web", template="nextjs"),
            FrontendSpec(name="admin", template="react"),
        ],
        backend="fastapi",
    )
    output = tmp_path / "myapp"
    render_project(config, output)

    content = (output / "kreator.yaml").read_text()
    assert "frontends:" in content
    assert "name: web" in content
    assert "template: nextjs" in content
    assert "name: admin" in content
    assert "template: react" in content


def test_render_project_single_frontend_kreator_yaml_compat(tmp_path: Path) -> None:
    config = KreatorConfig(name="myapp", frontend="nextjs", backend="fastapi")
    output = tmp_path / "myapp"
    render_project(config, output)

    content = (output / "kreator.yaml").read_text()
    assert "frontend: nextjs" in content
    assert "frontends:" not in content


def test_render_project_expo_only(tmp_path: Path) -> None:
    config = KreatorConfig(name="myapp", frontend="expo", backend="fastapi")
    output = tmp_path / "myapp"
    files = render_project(config, output)

    assert len(files) > 0
    assert (output / "apps" / "frontend" / "package.json").exists()
    assert (output / "apps" / "frontend" / "app.json").exists()
    assert (output / "apps" / "frontend" / "eas.json").exists()
    assert (output / "apps" / "frontend" / "src" / "app" / "_layout.tsx").exists()
    assert (output / "apps" / "frontend" / "src" / "components" / "LoginScreen.tsx").exists()

    assert not (output / "deploy" / "helm" / "frontend").exists()
    assert not (output / "deploy" / "argocd" / "apps" / "frontend.yaml").exists()


def test_render_project_helm_values_parameterized(tmp_path: Path) -> None:
    config = KreatorConfig(name="myapp", frontend="nextjs", backend="fastapi")
    output = tmp_path / "myapp"
    render_project(config, output)

    values = (output / "deploy" / "helm" / "frontend" / "values.yaml").read_text()
    assert "localhost:5001/myapp-frontend" in values
    assert "frontend.localhost" in values


def test_render_project_backend_helm_references_split_secrets(tmp_path: Path) -> None:
    config = KreatorConfig(name="myapp", frontend="nextjs", backend="fastapi")
    output = tmp_path / "myapp"
    render_project(config, output)

    values = (output / "deploy" / "helm" / "backend" / "values.yaml").read_text()
    assert "dbSecretName: myapp-db-credentials" in values
    assert "jwtSecretName: myapp-jwt-secret" in values
    assert "app-secrets" not in values


def test_fastapi_cors_credentials_false(tmp_path: Path) -> None:
    config = KreatorConfig(name="myapp", backend="fastapi")
    output = tmp_path / "myapp"
    render_project(config, output)

    main_py = (output / "apps" / "backend" / "app" / "main.py").read_text()
    assert "allow_credentials=False" in main_py
    assert "allow_credentials=True" not in main_py


def test_fastapi_no_alembic_dependency(tmp_path: Path) -> None:
    config = KreatorConfig(name="myapp", backend="fastapi")
    output = tmp_path / "myapp"
    render_project(config, output)

    pyproject = (output / "apps" / "backend" / "pyproject.toml").read_text()
    assert "alembic" not in pyproject


def test_fastapi_json_logger_version(tmp_path: Path) -> None:
    config = KreatorConfig(name="myapp", backend="fastapi")
    output = tmp_path / "myapp"
    render_project(config, output)

    pyproject = (output / "apps" / "backend" / "pyproject.toml").read_text()
    assert "python-json-logger>=3.1" in pyproject


def test_argocd_project_isolation(tmp_path: Path) -> None:
    config = KreatorConfig(name="snowfall", backend="fastapi")
    output = tmp_path / "snowfall"
    render_project(config, output)

    appproject = (output / "deploy" / "argocd" / "appproject.yaml").read_text()
    assert "name: snowfall" in appproject
    assert "namespace: snowfall" in appproject

    for app_file in (output / "deploy" / "argocd").rglob("*.yaml"):
        content = app_file.read_text()
        if "kind: Application" in content:
            assert "project: snowfall" in content, f"{app_file.name} uses wrong project"
            assert "project: default" not in content, f"{app_file.name} still references default"

    root_app = (output / "deploy" / "argocd" / "root-app.yaml").read_text()
    assert "namespace: argocd" in root_app

    backend_app = (output / "deploy" / "argocd" / "apps" / "backend.yaml").read_text()
    assert "namespace: snowfall" in backend_app

    claim = (output / "infrastructure" / "claims" / "database.yaml").read_text()
    assert "namespace: snowfall" in claim
    assert "namespace: default" not in claim

    jwt = (output / "secrets" / "raw" / "jwt-secret.yaml").read_text()
    assert "namespace: snowfall" in jwt
