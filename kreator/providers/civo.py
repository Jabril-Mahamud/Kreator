import logging
import time
from pathlib import Path

from kreator.core.platform import wait_for_crd
from kreator.core.shell import run

logger = logging.getLogger(__name__)


def setup_civo_api_key_secret(api_key: str) -> None:
    """Create the Civo API key secret in crossplane-system namespace."""
    run(["kubectl", "create", "namespace", "crossplane-system"], check=False)

    run(
        ["kubectl", "delete", "secret", "civo-api-key", "-n", "crossplane-system"],
        check=False,
    )

    run(
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
    run(["kubectl", "apply", "-f", "-"], input=provider_yaml)
    logger.info("civo provider installed, waiting for CRDs")

    _wait_for_provider_ready("provider-civo", timeout=180)


def _wait_for_provider_ready(name: str, timeout: int = 180) -> None:
    start = time.time()
    while time.time() - start < timeout:
        result = run(
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
        run(["kubectl", "apply", "-f", str(xrds)])
        wait_for_crd("databases.kreator.dev")

    provider_configs = infra_dir / "provider-configs"
    if provider_configs.is_dir():
        logger.info("applying provider configs")
        for f in provider_configs.glob("*.yaml"):
            run(["kubectl", "apply", "-f", str(f)], check=False)
        time.sleep(3)

    compositions_dir = infra_dir / "compositions" / "civo"
    if compositions_dir.is_dir():
        logger.info("applying civo compositions")
        run(["kubectl", "apply", "-f", str(compositions_dir)])
        time.sleep(3)

    claims = infra_dir / "claims"
    if claims.is_dir():
        logger.info("applying crossplane claims")
        run(["kubectl", "apply", "-f", str(claims)])


def wait_for_claims_ready(project_dir: Path, timeout: int = 600) -> None:
    """Wait for all Crossplane claims to become ready."""
    claims_dir = project_dir / "infrastructure" / "claims"
    if not claims_dir.is_dir():
        return

    logger.info("waiting for crossplane claims to be ready (this may take several minutes)")
    start = time.time()
    while time.time() - start < timeout:
        result = run(
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


def create_db_credentials_secret(config_name: str, namespace: str = "default") -> None:
    """Read Civo database connection details and create the db-credentials secret.

    The local composition creates this secret via Crossplane, but the Civo
    composition only exposes individual connection fields. This assembles
    DATABASE_URL and writes it to the same secret name the backend expects.
    """
    import base64
    import json

    conn_secret_name = f"{config_name}-db-conn"
    result = run(
        [
            "kubectl",
            "get",
            "secret",
            conn_secret_name,
            "-n",
            "crossplane-system",
            "-o",
            "jsonpath={.data}",
        ],
        capture=True,
        check=False,
    )

    if result.returncode == 0 and result.stdout.strip():
        data = json.loads(result.stdout)
        host = base64.b64decode(data.get("host", "")).decode()
        port = base64.b64decode(data.get("port", "")).decode() or "5432"
        username = base64.b64decode(data.get("username", "")).decode() or "postgres"
        password = base64.b64decode(data.get("password", "")).decode()
        database_url = f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{config_name}"
        logger.info("constructed database url from civo connection secret")
    else:
        logger.warning(
            "could not read connection secret %s, using placeholder database url",
            conn_secret_name,
        )
        database_url = f"postgresql+asyncpg://postgres:postgres@{config_name}-db:5432/{config_name}"

    secret_name = f"{config_name}-db-credentials"
    run(
        ["kubectl", "delete", "secret", secret_name, "-n", namespace],
        check=False,
    )
    run(
        [
            "kubectl",
            "create",
            "secret",
            "generic",
            secret_name,
            f"--from-literal=DATABASE_URL={database_url}",
            "-n",
            namespace,
        ]
    )
    logger.info("db credentials secret created for %s", config_name)


def delete_civo_resources(project_dir: Path) -> None:
    """Delete Crossplane claims and compositions for Civo."""
    infra_dir = project_dir / "infrastructure"

    claims = infra_dir / "claims"
    if claims.is_dir():
        logger.info("deleting crossplane claims")
        run(["kubectl", "delete", "-f", str(claims)], check=False)

    compositions_dir = infra_dir / "compositions" / "civo"
    if compositions_dir.is_dir():
        logger.info("deleting civo compositions")
        run(["kubectl", "delete", "-f", str(compositions_dir)], check=False)

    logger.info("waiting for resources to be cleaned up")
    time.sleep(30)
