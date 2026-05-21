import typer


def deploy(
    civo_api_key: str = typer.Option(
        None, "--civo-api-key", envvar="CIVO_API_KEY", help="Civo API key"
    ),
) -> None:
    """Deploy to cloud infrastructure via Crossplane."""
    typer.echo("kreator deploy is not yet implemented (coming in phase 3)")
    raise typer.Exit(1)
