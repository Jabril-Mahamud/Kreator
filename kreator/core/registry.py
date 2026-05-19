import subprocess

import typer

REGISTRY_NAME = "kind-registry"
REGISTRY_PORT = 5001


def _run_quiet(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def registry_running() -> bool:
    result = _run_quiet(
        ["docker", "inspect", "-f", "{{.State.Running}}", REGISTRY_NAME],
        check=False,
    )
    return result.stdout.strip() == "true"


def create_registry() -> None:
    if registry_running():
        typer.echo("Local registry already running")
        return

    typer.echo(f"Starting local registry on port {REGISTRY_PORT}...")
    _run_quiet(["docker", "rm", "-f", REGISTRY_NAME], check=False)
    _run_quiet(
        [
            "docker",
            "run",
            "-d",
            "--restart=always",
            "-p",
            f"{REGISTRY_PORT}:5000",
            "--network",
            "bridge",
            "--name",
            REGISTRY_NAME,
            "registry:2",
        ]
    )
    typer.echo("Registry started")


def connect_registry_to_kind(cluster_name: str) -> None:
    network = "kind"
    result = _run_quiet(
        [
            "docker",
            "inspect",
            "-f",
            "{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}",
            REGISTRY_NAME,
        ],
        check=False,
    )
    result2 = _run_quiet(
        ["docker", "network", "inspect", network, "-f", "{{.Id}}"],
        check=False,
    )

    if result.returncode == 0 and result2.returncode == 0:
        if result2.stdout.strip()[:12] not in result.stdout:
            _run_quiet(["docker", "network", "connect", network, REGISTRY_NAME], check=False)
            typer.echo("Connected registry to Kind network")
        else:
            typer.echo("Registry already on Kind network")


def delete_registry() -> None:
    typer.echo("Removing local registry...")
    _run_quiet(["docker", "rm", "-f", REGISTRY_NAME], check=False)
    typer.echo("Registry removed")


def get_registry_url() -> str:
    return f"localhost:{REGISTRY_PORT}"
