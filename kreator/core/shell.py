import subprocess


def run(
    cmd: list[str],
    check: bool = True,
    capture: bool = False,
    input: str | None = None,
    env: dict | None = None,
) -> subprocess.CompletedProcess:
    try:
        kwargs: dict = {"check": check, "text": True}
        if env is not None:
            kwargs["env"] = env
        if input is not None:
            kwargs["input"] = input
            kwargs["capture_output"] = True
        elif capture:
            kwargs["capture_output"] = True
        return subprocess.run(cmd, **kwargs)
    except subprocess.CalledProcessError as e:
        msg = f"Command failed: {' '.join(cmd)}"
        if e.stderr:
            msg += f"\n{e.stderr.strip()}"
        raise RuntimeError(msg) from e
    except FileNotFoundError:
        raise RuntimeError(f"Command not found: {cmd[0]}. Is it installed and on your PATH?")
