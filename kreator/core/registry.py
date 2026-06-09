import logging

from kreator.core.shell import run

logger = logging.getLogger(__name__)

REGISTRY_NAME = "kreator-registry"
REGISTRY_PORT = 5001


def _port_has_registry() -> bool:
    """Check if any container is already serving a registry on REGISTRY_PORT."""
    result = run(
        [
            "docker",
            "ps",
            "--filter",
            f"publish={REGISTRY_PORT}",
            "--format",
            "{{.Names}}",
        ],
        capture=True,
        check=False,
    )
    return bool(result.stdout.strip())


def registry_running() -> bool:
    result = run(
        ["docker", "inspect", "-f", "{{.State.Running}}", REGISTRY_NAME],
        capture=True,
        check=False,
    )
    return "true" in result.stdout


def start_registry() -> None:
    if registry_running():
        logger.info("registry already running on port %d", REGISTRY_PORT)
        return

    if _port_has_registry():
        logger.info("existing registry found on port %d, reusing it", REGISTRY_PORT)
        return

    result = run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"name=^/{REGISTRY_NAME}$",
            "--format",
            "{{.Names}}",
        ],
        capture=True,
    )
    if REGISTRY_NAME in result.stdout.split():
        run(["docker", "start", REGISTRY_NAME])
    else:
        run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                REGISTRY_NAME,
                "--restart",
                "always",
                "-p",
                f"127.0.0.1:{REGISTRY_PORT}:5000",
                "registry:2",
            ]
        )

    logger.info("registry started on localhost:%d", REGISTRY_PORT)


def stop_registry() -> None:
    if not registry_running():
        return
    run(["docker", "stop", REGISTRY_NAME], check=False)
    run(["docker", "rm", REGISTRY_NAME], check=False)
    logger.info("registry stopped")


def build_and_push(image_name: str, context_dir: str, registry_port: int = REGISTRY_PORT) -> str:
    tag = f"localhost:{registry_port}/{image_name.lower()}:latest"
    logger.info("building image: %s", tag)
    run(["docker", "build", "-t", tag, context_dir])
    logger.info("pushing image: %s", tag)
    run(["docker", "push", tag])
    return tag
