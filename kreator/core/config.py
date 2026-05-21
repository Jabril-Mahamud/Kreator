from pathlib import Path

from pydantic import BaseModel, field_validator

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


def discover_templates(kind: str) -> list[str]:
    """Scan templates/<kind>/ and return available template names."""
    template_dir = TEMPLATES_DIR / kind
    if not template_dir.is_dir():
        return []
    return sorted(
        d.name for d in template_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    )


class KreatorConfig(BaseModel):
    name: str
    frontend: str = "nextjs"
    backend: str = "fastapi"
    database: str = "postgres"
    provider: str = "civo"
    region: str = "lon1"

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.isidentifier() and not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError(
                f"Project name '{v}' must only contain alphanumeric, hyphens, or underscores"
            )
        if not v:
            raise ValueError("Project name cannot be empty")
        return v

    @field_validator("frontend")
    @classmethod
    def validate_frontend(cls, v: str) -> str:
        available = discover_templates("frontend")
        if v not in available:
            raise ValueError(f"Frontend '{v}' not found. Available: {', '.join(available)}")
        return v

    @field_validator("backend")
    @classmethod
    def validate_backend(cls, v: str) -> str:
        available = discover_templates("backend")
        if v not in available:
            raise ValueError(f"Backend '{v}' not found. Available: {', '.join(available)}")
        return v

    @field_validator("database")
    @classmethod
    def validate_database(cls, v: str) -> str:
        if v != "postgres":
            raise ValueError("Only 'postgres' is supported as a database")
        return v

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in ("civo", "local"):
            raise ValueError(f"Provider '{v}' not supported. Choose 'civo' or 'local'")
        return v


def load_config(path: Path) -> KreatorConfig:
    """Load and validate a kreator.yaml file."""
    import yaml

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid config file: {path}")
    return KreatorConfig(**data)
