from pathlib import Path

import typer

from kreator.core.config import load_config
from kreator.providers.civo import CivoProvider


def deploy_command(
    civo_api_key: str = typer.Option(
        "",
        "--civo-api-key",
        envvar="CIVO_API_KEY",
        help="Civo API key (or set CIVO_API_KEY env var)",
    ),
) -> None:
    """Provision real infrastructure and deploy."""
    config_path = Path.cwd() / "kreator.yaml"
    if not config_path.exists():
        typer.echo(
            "Error: kreator.yaml not found. Run this from a kreator project directory.",
            err=True,
        )
        raise typer.Exit(1)

    config = load_config(config_path)
    project_dir = Path.cwd()

    if config.provider != "civo":
        typer.echo(
            f"Error: deploy is for cloud providers. Provider is '{config.provider}'. "
            "Use 'kreator dev' for local development.",
            err=True,
        )
        raise typer.Exit(1)

    import os

    if civo_api_key:
        os.environ["CIVO_API_KEY"] = civo_api_key

    provider = CivoProvider(config, project_dir)
    provider.setup()
