import typer


def destroy() -> None:
    """Tear down cloud infrastructure."""
    typer.echo("kreator destroy is not yet implemented (coming in phase 3)")
    raise typer.Exit(1)
