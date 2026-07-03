import subprocess
import sys


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
        else:
            # Pipe stderr (stdout still streams) so failures can report it.
            kwargs["stderr"] = subprocess.PIPE
        result = subprocess.run(cmd, **kwargs)
        if kwargs.get("stderr") == subprocess.PIPE and result.stderr:
            sys.stderr.write(result.stderr)
        return result
    except subprocess.CalledProcessError as e:
        msg = f"Command failed: {' '.join(cmd)}"
        if e.stderr:
            msg += f"\n{e.stderr.strip()}"
        raise RuntimeError(msg) from e
    except FileNotFoundError:
        raise RuntimeError(f"Command not found: {cmd[0]}. Is it installed and on your PATH?")
