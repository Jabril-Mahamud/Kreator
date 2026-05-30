import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from kreator.core.config import TEMPLATES_DIR, KreatorConfig

PLATFORM_DIR_MAP: dict[str, str] = {
    "crossplane/xrds": "infrastructure/xrds",
    "crossplane/compositions": "infrastructure/compositions",
    "crossplane/claims": "infrastructure/claims",
    "crossplane/provider-configs": "infrastructure/provider-configs",
    "helm": "deploy/helm",
    "argocd": "deploy/argocd",
    "sealed-secrets": "secrets/sealed",
    "ingress": "deploy/ingress",
    "observability": "deploy/observability",
}


def render_template_dir(template_dir: Path, output_dir: Path, context: dict) -> list[Path]:
    """Walk a template directory, render .j2 files, copy the rest. Returns list of created files."""
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )

    created: list[Path] = []

    for source in sorted(template_dir.rglob("*")):
        if source.is_dir():
            continue

        rel = source.relative_to(template_dir)
        rel_str = str(rel)

        if rel_str.endswith(".j2"):
            dest = output_dir / rel_str[:-3]
            template = env.get_template(str(rel))
            rendered = template.render(**context)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(rendered)
            created.append(dest)
        else:
            dest = output_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            created.append(dest)

    return created


def render_platform(output_dir: Path, context: dict) -> list[Path]:
    """Render platform templates into their correct output directories."""
    platform_dir = TEMPLATES_DIR / "platform"
    if not platform_dir.is_dir():
        return []

    created: list[Path] = []

    for source in sorted(platform_dir.rglob("*")):
        if source.is_dir():
            continue

        rel = source.relative_to(platform_dir)
        rel_str = str(rel)

        mapped_rel = rel_str
        for src_prefix, dest_prefix in PLATFORM_DIR_MAP.items():
            if rel_str.startswith(src_prefix):
                mapped_rel = dest_prefix + rel_str[len(src_prefix) :]
                break

        if mapped_rel.endswith(".j2"):
            mapped_rel = mapped_rel[:-3]
            env = Environment(
                loader=FileSystemLoader(str(platform_dir)),
                undefined=StrictUndefined,
                keep_trailing_newline=True,
            )
            template = env.get_template(rel_str)
            rendered = template.render(**context)
            dest = output_dir / mapped_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(rendered)
            created.append(dest)
        else:
            dest = output_dir / mapped_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            created.append(dest)

    return created


def render_project(config: KreatorConfig, output_dir: Path) -> list[Path]:
    """Render the full project from templates into output_dir."""
    import secrets as _secrets

    context = {
        "name": config.name,
        "frontend": config.frontend,
        "backend": config.backend,
        "database": config.database,
        "provider": config.provider,
        "region": config.region,
        "repo_url": config.repo_url or f"https://github.com/OWNER/{config.name}.git",
        "jwt_secret": _secrets.token_urlsafe(32),
    }

    created: list[Path] = []

    project_templates = TEMPLATES_DIR / "project"
    if project_templates.is_dir():
        created += render_template_dir(project_templates, output_dir, context)

    frontend_dir = TEMPLATES_DIR / "frontend" / config.frontend
    if frontend_dir.is_dir():
        created += render_template_dir(frontend_dir, output_dir / "apps" / "frontend", context)

    backend_dir = TEMPLATES_DIR / "backend" / config.backend
    if backend_dir.is_dir():
        created += render_template_dir(backend_dir, output_dir / "apps" / "backend", context)

    created += render_platform(output_dir, context)

    (output_dir / "secrets" / "raw").mkdir(parents=True, exist_ok=True)
    (output_dir / "secrets" / "raw" / ".gitkeep").touch()
    created.append(output_dir / "secrets" / "raw" / ".gitkeep")

    return created
