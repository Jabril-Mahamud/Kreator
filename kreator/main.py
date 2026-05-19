import typer

from kreator.commands.deploy import deploy_command
from kreator.commands.destroy import destroy_command
from kreator.commands.dev import dev_command
from kreator.commands.init import init_command

app = typer.Typer(
    name="kreator",
    help="Scaffold deployment-ready full-stack apps with Kubernetes, Crossplane, and ArgoCD.",
    no_args_is_help=True,
)

app.command("init")(init_command)
app.command("dev")(dev_command)
app.command("deploy")(deploy_command)
app.command("destroy")(destroy_command)

if __name__ == "__main__":
    app()
