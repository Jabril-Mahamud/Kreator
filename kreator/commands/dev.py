import typer


def dev(
    destroy: bool = typer.Option(False, "--destroy", help="Tear down the local dev environment"),
    with_observability: bool = typer.Option(
        False, "--with-observability", help="Install the LGTM observability stack"
    ),
) -> None:
    """Spin up local Kind cluster with ArgoCD and Crossplane."""
    typer.echo("kreator dev is not yet implemented (coming in phase 2)")
    raise typer.Exit(1)
