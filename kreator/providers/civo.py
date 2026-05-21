import logging
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def _run(
    cmd: list[str],
    check: bool = True,
    capture: bool = False,
    input: str | None = None,
) -> subprocess.CompletedProcess:
    try:
        kwargs: dict = {"check": check, "text": True}
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


def setup_civo_api_key_secret(api_key: str) -> None:
    """Create the Civo API key secret in crossplane-system namespace."""
    _run(["kubectl", "create", "namespace", "crossplane-system"], check=False)

    _run(
        ["kubectl", "delete", "secret", "civo-api-key", "-n", "crossplane-system"],
        check=False,
    )

    _run(
        [
            "kubectl",
            "create",
            "secret",
            "generic",
            "civo-api-key",
            "--from-literal",
            f"credentials={api_key}",
            "-n",
            "crossplane-system",
        ]
    )
    logger.info("civo api key secret created")


def install_crossplane_provider_civo() -> None:
    """Install the Crossplane Civo provider."""
    provider_yaml = """
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-civo
spec:
  package: xpkg.upbound.io/civo/provider-civo:v0.3.0
"""
    _run(["kubectl", "apply", "-f", "-"], input=provider_yaml)
    logger.info("civo provider installed, waiting for CRDs")

    _wait_for_provider_ready("provider-civo", timeout=180)


def _wait_for_provider_ready(name: str, timeout: int = 180) -> None:
    start = time.time()
    while time.time() - start < timeout:
        result = _run(
            [
                "kubectl",
                "get",
                "provider",
                name,
                "-o",
                "jsonpath={.status.conditions[?(@.type=='Healthy')].status}",
            ],
            capture=True,
            check=False,
        )
        if result.returncode == 0 and "True" in result.stdout:
            logger.info("provider %s is healthy", name)
            return
        time.sleep(5)
    raise RuntimeError(f"Provider {name} not healthy after {timeout}s")


def apply_civo_manifests(project_dir: Path) -> None:
    """Apply Crossplane resources for Civo deployment."""
    infra_dir = project_dir / "infrastructure"

    xrds = infra_dir / "xrds"
    if xrds.is_dir():
        logger.info("applying crossplane xrds")
        _run(["kubectl", "apply", "-f", str(xrds)])
        time.sleep(5)

    provider_configs = infra_dir / "provider-configs"
    if provider_configs.is_dir():
        logger.info("applying provider configs")
        for f in provider_configs.glob("*.yaml"):
            _run(["kubectl", "apply", "-f", str(f)], check=False)
        time.sleep(3)

    compositions_dir = infra_dir / "compositions" / "civo"
    if compositions_dir.is_dir():
        logger.info("applying civo compositions")
        _run(["kubectl", "apply", "-f", str(compositions_dir)])
        time.sleep(3)

    secrets_dir = project_dir / "secrets" / "sealed"
    if secrets_dir.is_dir():
        logger.info("applying secrets")
        _run(["kubectl", "apply", "-f", str(secrets_dir)])

    claims = infra_dir / "claims"
    if claims.is_dir():
        logger.info("applying crossplane claims")
        _run(["kubectl", "apply", "-f", str(claims)])


def wait_for_claims_ready(project_dir: Path, timeout: int = 600) -> None:
    """Wait for all Crossplane claims to become ready."""
    claims_dir = project_dir / "infrastructure" / "claims"
    if not claims_dir.is_dir():
        return

    logger.info("waiting for crossplane claims to be ready (this may take several minutes)")
    start = time.time()
    while time.time() - start < timeout:
        result = _run(
            [
                "kubectl",
                "get",
                "databases.kreator.dev",
                "-o",
                "jsonpath={.items[*].status.conditions[?(@.type=='Ready')].status}",
            ],
            capture=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            statuses = result.stdout.split()
            if all(s == "True" for s in statuses):
                logger.info("all claims ready")
                return
        time.sleep(10)
    raise RuntimeError(f"Claims not ready after {timeout}s")


def delete_civo_resources(project_dir: Path) -> None:
    """Delete Crossplane claims and compositions for Civo."""
    infra_dir = project_dir / "infrastructure"

    claims = infra_dir / "claims"
    if claims.is_dir():
        logger.info("deleting crossplane claims")
        _run(["kubectl", "delete", "-f", str(claims)], check=False)

    compositions_dir = infra_dir / "compositions" / "civo"
    if compositions_dir.is_dir():
        logger.info("deleting civo compositions")
        _run(["kubectl", "delete", "-f", str(compositions_dir)], check=False)

    logger.info("waiting for resources to be cleaned up")
    time.sleep(30)
