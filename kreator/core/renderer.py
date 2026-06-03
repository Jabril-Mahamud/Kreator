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

FRONTEND_HELM_PREFIX = "helm/frontend/"
FRONTEND_ARGOCD_FILE = "argocd/apps/frontend.yaml.j2"


def _render_path(rel_str: str, context: dict) -> str:
    """Render Jinja2 expressions in a file path (e.g. '{{ frontend_name }}' in filenames)."""
    if "{{" in rel_str:
        env = Environment(undefined=StrictUndefined)
        return env.from_string(rel_str).render(**context)
    return rel_str


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
        out_rel = _render_path(rel_str, context)

        if out_rel.endswith(".j2"):
            dest = output_dir / out_rel[:-3]
            template = env.get_template(str(rel))
            rendered = template.render(**context)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(rendered)
            created.append(dest)
        else:
            dest = output_dir / out_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            created.append(dest)

    return created


def _is_frontend_helm_path(rel_str: str) -> bool:
    return rel_str.startswith(FRONTEND_HELM_PREFIX)


def _is_frontend_argocd_path(rel_str: str) -> bool:
    return rel_str == FRONTEND_ARGOCD_FILE


def _render_platform_file(
    platform_dir: Path, rel_str: str, mapped_rel: str, output_dir: Path, context: dict
) -> Path:
    """Render or copy a single platform file. Returns the created path."""
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
        return dest
    else:
        source = platform_dir / rel_str
        dest = output_dir / mapped_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        return dest


def render_platform(output_dir: Path, context: dict, config: KreatorConfig) -> list[Path]:
    """Render platform templates into their correct output directories."""
    platform_dir = TEMPLATES_DIR / "platform"
    if not platform_dir.is_dir():
        return []

    created: list[Path] = []
    web_frontends = config.web_frontends

    for source in sorted(platform_dir.rglob("*")):
        if source.is_dir():
            continue

        rel = source.relative_to(platform_dir)
        rel_str = str(rel)

        if _is_frontend_helm_path(rel_str) or _is_frontend_argocd_path(rel_str):
            for fe in web_frontends:
                fe_context = {
                    **context,
                    "frontend_name": fe.name,
                    "frontend_template": fe.template,
                }

                if _is_frontend_helm_path(rel_str):
                    suffix = rel_str[len(FRONTEND_HELM_PREFIX) :]
                    mapped_rel = f"deploy/helm/{fe.name}/{suffix}"
                else:
                    mapped_rel = f"deploy/argocd/apps/{fe.name}.yaml.j2"

                created.append(
                    _render_platform_file(platform_dir, rel_str, mapped_rel, output_dir, fe_context)
                )
            continue

        mapped_rel = rel_str
        for src_prefix, dest_prefix in PLATFORM_DIR_MAP.items():
            if rel_str.startswith(src_prefix):
                mapped_rel = dest_prefix + rel_str[len(src_prefix) :]
                break

        created.append(
            _render_platform_file(platform_dir, rel_str, mapped_rel, output_dir, context)
        )

    return created


def render_project(config: KreatorConfig, output_dir: Path) -> list[Path]:
    """Render the full project from templates into output_dir."""
    import secrets as _secrets

    frontends = config.frontends or []

    context = {
        "name": config.name,
        "frontend": frontends[0].template if frontends else "nextjs",
        "frontends": frontends,
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

    for fe in frontends:
        fe_dir = TEMPLATES_DIR / "frontend" / fe.template
        if fe_dir.is_dir():
            fe_context = {**context, "frontend_name": fe.name, "frontend_template": fe.template}
            created += render_template_dir(fe_dir, output_dir / "apps" / fe.name, fe_context)

    backend_dir = TEMPLATES_DIR / "backend" / config.backend
    if backend_dir.is_dir():
        created += render_template_dir(backend_dir, output_dir / "apps" / "backend", context)

    created += render_platform(output_dir, context, config)

    ci_dir = TEMPLATES_DIR / "ci" / "mobile"
    for fe in config.mobile_frontends:
        if ci_dir.is_dir():
            fe_context = {**context, "frontend_name": fe.name, "frontend_template": fe.template}
            created += render_template_dir(ci_dir, output_dir, fe_context)

    (output_dir / "secrets" / "raw").mkdir(parents=True, exist_ok=True)
    (output_dir / "secrets" / "raw" / ".gitkeep").touch()
    created.append(output_dir / "secrets" / "raw" / ".gitkeep")

    return created
