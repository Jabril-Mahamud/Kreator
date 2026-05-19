from pathlib import Path

import typer

from kreator.core.config import load_config


def destroy_command() -> None:
    """Tear down all provisioned resources."""
    config_path = Path.cwd() / "kreator.yaml"
    if not config_path.exists():
        typer.echo(
            "Error: kreator.yaml not found. Run this from a kreator project directory.",
            err=True,
        )
        raise typer.Exit(1)

    config = load_config(config_path)
    project_dir = Path.cwd()

    if config.provider == "local":
        from kreator.providers.local import LocalProvider

        provider = LocalProvider(config, project_dir)
    elif config.provider == "civo":
        from kreator.providers.civo import CivoProvider

        provider = CivoProvider(config, project_dir)
    else:
        typer.echo(f"Error: unknown provider '{config.provider}'", err=True)
        raise typer.Exit(1)

    typer.echo(f"Destroying '{config.name}' ({config.provider})...")
    provider.destroy()
    typer.echo("All resources destroyed")
