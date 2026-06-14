import re
from pathlib import Path

from pydantic import BaseModel, field_validator, model_validator

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

TEMPLATE_PLATFORMS: dict[str, str] = {
    "nextjs": "web",
    "react": "web",
    "expo": "mobile",
}


def slugify_name(v: str) -> str:
    """Normalize a name into a valid RFC 1123 label (DNS-safe Kubernetes name).

    Lowercases, collapses runs of non-alphanumeric characters into single
    hyphens, and strips leading/trailing hyphens. Returns "" if nothing valid
    remains.
    """
    s = re.sub(r"[^a-z0-9]+", "-", v.strip().lower())
    return s.strip("-")


def discover_templates(kind: str) -> list[str]:
    """Scan templates/<kind>/ and return available template names."""
    template_dir = TEMPLATES_DIR / kind
    if not template_dir.is_dir():
        return []
    return sorted(
        d.name for d in template_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    )


class FrontendSpec(BaseModel):
    name: str
    template: str
    platform: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]*$", v):
            raise ValueError(f"Frontend name '{v}' must be lowercase alphanumeric with hyphens")
        if v == "backend":
            raise ValueError("Frontend name cannot be 'backend'")
        return v


class KreatorConfig(BaseModel):
    name: str
    frontend: str | None = "nextjs"
    frontends: list[FrontendSpec] | None = None
    backend: str = "fastapi"
    database: str = "postgres"
    provider: str = "civo"
    region: str = "lon1"
    repo_url: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Project name cannot be empty")
        # The name is used verbatim as a Kubernetes namespace and resource
        # names, which must be lowercase RFC 1123 labels. Normalize it so an
        # input like "JobHunterApp" or "My_App" can never produce invalid
        # manifests downstream.
        slug = slugify_name(v)
        if not slug:
            raise ValueError(f"Project name '{v}' must contain at least one alphanumeric character")
        return slug

    @model_validator(mode="after")
    def normalize_frontends(self) -> "KreatorConfig":
        available = discover_templates("frontend")

        if self.frontends:
            for fe in self.frontends:
                if fe.template not in available:
                    raise ValueError(
                        f"Frontend template '{fe.template}' not found. "
                        f"Available: {', '.join(available)}"
                    )
                if not fe.platform:
                    fe.platform = TEMPLATE_PLATFORMS.get(fe.template, "web")

            names = [fe.name for fe in self.frontends]
            if len(names) != len(set(names)):
                raise ValueError("Frontend names must be unique")

            self.frontend = None
        else:
            template = self.frontend or "nextjs"
            if template not in available:
                raise ValueError(
                    f"Frontend '{template}' not found. Available: {', '.join(available)}"
                )
            platform = TEMPLATE_PLATFORMS.get(template, "web")
            self.frontends = [FrontendSpec(name="frontend", template=template, platform=platform)]

        return self

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

    @property
    def web_frontends(self) -> list[FrontendSpec]:
        return [fe for fe in (self.frontends or []) if fe.platform == "web"]

    @property
    def mobile_frontends(self) -> list[FrontendSpec]:
        return [fe for fe in (self.frontends or []) if fe.platform == "mobile"]


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
