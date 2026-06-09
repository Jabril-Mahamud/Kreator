import typer

from kreator.commands.deploy import deploy
from kreator.commands.destroy import destroy
from kreator.commands.dev import dev
from kreator.commands.doctor import doctor
from kreator.commands.init import init

app = typer.Typer(
    name="kreator",
    help="Scaffold deployment-ready full-stack apps with Kubernetes, Crossplane, and ArgoCD.",
    no_args_is_help=True,
)

app.command()(init)
app.command()(dev)
app.command()(deploy)
app.command()(destroy)
app.command()(doctor)

if __name__ == "__main__":
    app()
