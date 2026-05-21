import pytest
from pydantic import ValidationError

from kreator.core.config import KreatorConfig, discover_templates, load_config


def test_discover_frontend_templates() -> None:
    templates = discover_templates("frontend")
    assert "nextjs" in templates
    assert "react" in templates


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
    assert config.frontend == "nextjs"
    assert config.backend == "fastapi"
    assert config.database == "postgres"
    assert config.provider == "civo"
    assert config.region == "lon1"


def test_all_backend_options() -> None:
    for backend in ["fastapi", "go", "express"]:
        config = KreatorConfig(name="test", backend=backend)
        assert config.backend == backend


def test_all_frontend_options() -> None:
    for frontend in ["nextjs", "react"]:
        config = KreatorConfig(name="test", frontend=frontend)
        assert config.frontend == frontend


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
    assert config.frontend == "nextjs"


def test_load_config_missing_file(tmp_path: pytest.TempPathFactory) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nonexistent.yaml")
