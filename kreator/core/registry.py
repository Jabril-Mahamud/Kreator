import logging
import subprocess

logger = logging.getLogger(__name__)

REGISTRY_NAME = "kreator-registry"
REGISTRY_PORT = 5001


def _run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, check=check, capture_output=capture, text=True)
    except subprocess.CalledProcessError as e:
        msg = f"Command failed: {' '.join(cmd)}"
        if e.stderr:
            msg += f"\n{e.stderr.strip()}"
        raise RuntimeError(msg) from e
    except FileNotFoundError:
        raise RuntimeError(f"Command not found: {cmd[0]}. Is it installed and on your PATH?")


def registry_running() -> bool:
    result = _run(
        ["docker", "inspect", "-f", "{{.State.Running}}", REGISTRY_NAME],
        capture=True,
        check=False,
    )
    return "true" in result.stdout


def start_registry() -> None:
    if registry_running():
        logger.info("registry already running on port %d", REGISTRY_PORT)
        return

    result = _run(
        ["docker", "ps", "-a", "--filter", f"name={REGISTRY_NAME}", "--format", "{{.Names}}"],
        capture=True,
    )
    if REGISTRY_NAME in result.stdout:
        _run(["docker", "start", REGISTRY_NAME])
    else:
        _run(
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
    _run(["docker", "stop", REGISTRY_NAME], check=False)
    _run(["docker", "rm", REGISTRY_NAME], check=False)
    logger.info("registry stopped")


def build_and_push(image_name: str, context_dir: str, registry_port: int = REGISTRY_PORT) -> str:
    tag = f"localhost:{registry_port}/{image_name}:latest"
    logger.info("building image: %s", tag)
    _run(["docker", "build", "-t", tag, context_dir])
    logger.info("pushing image: %s", tag)
    _run(["docker", "push", tag])
    return tag
