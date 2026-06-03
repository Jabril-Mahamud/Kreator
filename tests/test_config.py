import pytest
from pydantic import ValidationError

from kreator.core.config import FrontendSpec, KreatorConfig, discover_templates, load_config


def test_discover_frontend_templates() -> None:
    templates = discover_templates("frontend")
    assert "nextjs" in templates
    assert "react" in templates
    assert "expo" in templates


def test_discover_backend_templates() -> None:
    templates = discover_templates("backend")
    assert "fastapi" in templates
    assert "go" in templates
    assert "express" in templates


def test_discover_nonexistent_kind() -> None:
    templates = discover_templates("nonexistent")
    assert templates == []


def test_valid_config() -> None:
    config = KreatorConfig(name="my-app", frontend="nextjs", backend="fastapi")
    assert config.name == "my-app"
    assert config.backend == "fastapi"
    assert config.database == "postgres"
    assert config.provider == "civo"
    assert config.region == "lon1"
    assert config.repo_url == ""
    assert len(config.frontends) == 1
    assert config.frontends[0].name == "frontend"
    assert config.frontends[0].template == "nextjs"
    assert config.frontends[0].platform == "web"


def test_config_backwards_compat_frontend_field() -> None:
    config = KreatorConfig(name="test", frontend="react")
    assert config.frontends[0].template == "react"
    assert config.frontends[0].name == "frontend"
    assert config.frontends[0].platform == "web"


def test_config_with_repo_url() -> None:
    config = KreatorConfig(name="my-app", repo_url="https://github.com/me/my-app.git")
    assert config.repo_url == "https://github.com/me/my-app.git"


def test_all_backend_options() -> None:
    for backend in ["fastapi", "go", "express"]:
        config = KreatorConfig(name="test", backend=backend)
        assert config.backend == backend


def test_all_frontend_options() -> None:
    for frontend in ["nextjs", "react", "expo"]:
        config = KreatorConfig(name="test", frontend=frontend)
        assert config.frontends[0].template == frontend


def test_invalid_backend() -> None:
    with pytest.raises(ValidationError, match="not found"):
        KreatorConfig(name="test", backend="django")


def test_invalid_frontend() -> None:
    with pytest.raises(ValidationError, match="not found"):
        KreatorConfig(name="test", frontend="svelte")


def test_invalid_database() -> None:
    with pytest.raises(ValidationError, match="postgres"):
        KreatorConfig(name="test", database="mysql")


def test_invalid_provider() -> None:
    with pytest.raises(ValidationError, match="not supported"):
        KreatorConfig(name="test", provider="aws")


def test_empty_name() -> None:
    with pytest.raises(ValidationError):
        KreatorConfig(name="")


def test_load_config(tmp_path: pytest.TempPathFactory) -> None:
    config_file = tmp_path / "kreator.yaml"
    config_file.write_text(
        "name: test-app\nfrontend: nextjs\nbackend: fastapi\nprovider: civo\nregion: lon1\n"
    )
    config = load_config(config_file)
    assert config.name == "test-app"
    assert config.frontends[0].template == "nextjs"


def test_load_config_missing_file(tmp_path: pytest.TempPathFactory) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nonexistent.yaml")


def test_multi_frontend_config() -> None:
    config = KreatorConfig(
        name="test",
        frontend=None,
        frontends=[
            FrontendSpec(name="web", template="nextjs"),
            FrontendSpec(name="mobile", template="expo"),
        ],
    )
    assert len(config.frontends) == 2
    assert config.frontends[0].platform == "web"
    assert config.frontends[1].platform == "mobile"
    assert config.frontend is None


def test_multi_frontend_web_mobile_helpers() -> None:
    config = KreatorConfig(
        name="test",
        frontend=None,
        frontends=[
            FrontendSpec(name="web", template="nextjs"),
            FrontendSpec(name="mobile", template="expo"),
        ],
    )
    assert len(config.web_frontends) == 1
    assert config.web_frontends[0].name == "web"
    assert len(config.mobile_frontends) == 1
    assert config.mobile_frontends[0].name == "mobile"


def test_multi_frontend_duplicate_names() -> None:
    with pytest.raises(ValidationError, match="unique"):
        KreatorConfig(
            name="test",
            frontend=None,
            frontends=[
                FrontendSpec(name="web", template="nextjs"),
                FrontendSpec(name="web", template="react"),
            ],
        )


def test_multi_frontend_invalid_template() -> None:
    with pytest.raises(ValidationError, match="not found"):
        KreatorConfig(
            name="test",
            frontend=None,
            frontends=[FrontendSpec(name="web", template="svelte")],
        )


def test_frontend_name_validation() -> None:
    with pytest.raises(ValidationError, match="lowercase"):
        FrontendSpec(name="Web", template="nextjs")

    with pytest.raises(ValidationError, match="backend"):
        FrontendSpec(name="backend", template="nextjs")


def test_platform_derivation() -> None:
    config = KreatorConfig(name="test", frontend="expo")
    assert config.frontends[0].platform == "mobile"

    config = KreatorConfig(name="test", frontend="nextjs")
    assert config.frontends[0].platform == "web"


def test_load_config_multi_frontend(tmp_path: pytest.TempPathFactory) -> None:
    config_file = tmp_path / "kreator.yaml"
    config_file.write_text(
        "name: test-app\n"
        "frontends:\n"
        "  - name: web\n"
        "    template: nextjs\n"
        "  - name: mobile\n"
        "    template: expo\n"
        "backend: fastapi\n"
    )
    config = load_config(config_file)
    assert len(config.frontends) == 2
    assert config.frontends[0].name == "web"
    assert config.frontends[1].name == "mobile"
