import re
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator


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
        if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", v):
            raise ValueError(
                "name must be lowercase alphanumeric with hyphens only, "
                "cannot start or end with a hyphen"
            )
        return v

    @field_validator("frontend")
    @classmethod
    def validate_frontend(cls, v: str) -> str:
        allowed = {"nextjs"}
        if v not in allowed:
            raise ValueError(f"frontend must be one of: {', '.join(sorted(allowed))}")
        return v

    @field_validator("backend")
    @classmethod
    def validate_backend(cls, v: str) -> str:
        allowed = {"fastapi"}
        if v not in allowed:
            raise ValueError(f"backend must be one of: {', '.join(sorted(allowed))}")
        return v

    @field_validator("database")
    @classmethod
    def validate_database(cls, v: str) -> str:
        allowed = {"postgres"}
        if v not in allowed:
            raise ValueError(f"database must be one of: {', '.join(sorted(allowed))}")
        return v

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = {"civo", "local"}
        if v not in allowed:
            raise ValueError(f"provider must be one of: {', '.join(sorted(allowed))}")
        return v


def load_config(path: Path) -> KreatorConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    return KreatorConfig(**data)


def save_config(config: KreatorConfig, path: Path) -> None:
    data = config.model_dump()
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
