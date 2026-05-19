import pytest
from pydantic import ValidationError

from kreator.core.config import KreatorConfig


def test_valid_config_defaults():
    config = KreatorConfig(name="my-app")
    assert config.name == "my-app"
    assert config.frontend == "nextjs"
    assert config.backend == "fastapi"
    assert config.database == "postgres"
    assert config.provider == "civo"
    assert config.region == "lon1"


def test_valid_config_all_fields():
    config = KreatorConfig(
        name="test-project",
        frontend="nextjs",
        backend="fastapi",
        database="postgres",
        provider="local",
        region="lon1",
    )
    assert config.name == "test-project"
    assert config.provider == "local"


def test_invalid_name_uppercase():
    with pytest.raises(ValidationError, match="lowercase alphanumeric"):
        KreatorConfig(name="MyApp")


def test_invalid_name_underscore():
    with pytest.raises(ValidationError, match="lowercase alphanumeric"):
        KreatorConfig(name="my_app")


def test_invalid_name_starts_with_hyphen():
    with pytest.raises(ValidationError, match="lowercase alphanumeric"):
        KreatorConfig(name="-my-app")


def test_invalid_name_ends_with_hyphen():
    with pytest.raises(ValidationError, match="lowercase alphanumeric"):
        KreatorConfig(name="my-app-")


def test_invalid_name_empty():
    with pytest.raises(ValidationError, match="lowercase alphanumeric"):
        KreatorConfig(name="")


def test_invalid_frontend():
    with pytest.raises(ValidationError, match="frontend must be one of"):
        KreatorConfig(name="test", frontend="react")


def test_invalid_backend():
    with pytest.raises(ValidationError, match="backend must be one of"):
        KreatorConfig(name="test", backend="express")


def test_invalid_provider():
    with pytest.raises(ValidationError, match="provider must be one of"):
        KreatorConfig(name="test", provider="aws")


def test_model_dump():
    config = KreatorConfig(name="my-app")
    data = config.model_dump()
    assert data == {
        "name": "my-app",
        "frontend": "nextjs",
        "backend": "fastapi",
        "database": "postgres",
        "provider": "civo",
        "region": "lon1",
    }
