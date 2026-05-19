import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def render_template_dir(source: Path, output: Path, context: dict) -> None:
    env = Environment(
        loader=FileSystemLoader(str(source)),
        keep_trailing_newline=True,
    )

    for src_path in sorted(source.rglob("*")):
        rel = src_path.relative_to(source)
        rendered_rel = Path(*[_render_path_segment(seg, context) for seg in rel.parts])

        dest = output / rendered_rel

        if src_path.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)

        if src_path.name.endswith(".j2"):
            dest = dest.parent / dest.name.removesuffix(".j2")
            template = env.get_template(str(rel))
            content = template.render(**context)
            dest.write_text(content)
        else:
            shutil.copy2(src_path, dest)


def _render_path_segment(segment: str, context: dict) -> str:
    if "{{" in segment and "}}" in segment:
        env = Environment()
        template = env.from_string(segment)
        return template.render(**context)
    return segment
