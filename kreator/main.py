import typer

app = typer.Typer(
    name="kreator",
    help="Scaffold deployment-ready full-stack applications with Kubernetes, Crossplane, and ArgoCD.",
    no_args_is_help=True,
)


@app.command()
def init(name: str = typer.Argument(help="Project name (lowercase, alphanumeric, hyphens)")) -> None:
    """Scaffold a new project."""
    typer.echo(f"kreator init {name} - not implemented yet")


@app.command()
def dev() -> None:
    """Spin up local Kind cluster and deploy via ArgoCD + Crossplane."""
    typer.echo("kreator dev - not implemented yet")


@app.command()
def deploy() -> None:
    """Provision real infrastructure and deploy."""
    typer.echo("kreator deploy - not implemented yet")


if __name__ == "__main__":
    app()
