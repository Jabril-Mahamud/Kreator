import logging
import sys
from pathlib import Path

import typer

from kreator.core.config import load_config
from kreator.providers.civo import delete_civo_resources


def destroy() -> None:
    """Tear down cloud infrastructure."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stdout,
    )

    project_dir = Path.cwd()
    config_path = project_dir / "kreator.yaml"

    if not config_path.exists():
        typer.echo(
            "Error: kreator.yaml not found. Run this from a kreator project directory.",
            err=True,
        )
        raise typer.Exit(1)

    config = load_config(config_path)

    if config.provider != "civo":
        typer.echo(
            f"Error: kreator destroy only supports civo provider, got '{config.provider}'",
            err=True,
        )
        raise typer.Exit(1)

    typer.echo(f"Destroying Civo resources for '{config.name}'...")
    delete_civo_resources(project_dir)
    typer.echo("Done. Civo resources have been cleaned up.")
