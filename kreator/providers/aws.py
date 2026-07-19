import configparser
import logging
import time
from pathlib import Path

from kreator.core.platform import wait_for_crd, wait_for_provider_ready
from kreator.core.shell import run

logger = logging.getLogger(__name__)

AWS_PROVIDER_VERSION = "v2.6.1"


def validate_aws_credentials_file(credentials_path: Path) -> None:
    """Validate an AWS credentials file without exposing its contents.

    Expects INI format with a [default] section containing aws_access_key_id
    and aws_secret_access_key. Raises ValueError with a clear message on a
    missing or malformed file; never logs or includes key material.
    """
    if not credentials_path.is_file():
        raise ValueError(f"AWS credentials file not found: {credentials_path}")

    parser = configparser.ConfigParser()
    try:
        parser.read(credentials_path)
    except configparser.Error:
        raise ValueError(
            f"AWS credentials file {credentials_path} is not valid INI format"
        ) from None

    if "default" not in parser:
        raise ValueError(f"AWS credentials file {credentials_path} has no [default] section")

    for key in ("aws_access_key_id", "aws_secret_access_key"):
        if not parser["default"].get(key):
            raise ValueError(f"AWS credentials file {credentials_path} is missing {key}")


def setup_aws_credentials_secret(credentials_path: Path) -> None:
    """Create the AWS credentials secret in crossplane-system namespace.

    The file content is passed to kubectl via --from-file so key material
    never appears in logs or process arguments.
    """
    validate_aws_credentials_file(credentials_path)

    run(["kubectl", "create", "namespace", "crossplane-system"], check=False)

    run(
        ["kubectl", "delete", "secret", "aws-credentials", "-n", "crossplane-system"],
        check=False,
    )

    run(
        [
            "kubectl",
            "create",
            "secret",
            "generic",
            "aws-credentials",
            f"--from-file=creds={credentials_path}",
            "-n",
            "crossplane-system",
        ]
    )
    logger.info("aws credentials secret created")


# Family must come first; the service providers depend on its CRDs.
AWS_PROVIDERS = ("provider-family-aws", "provider-aws-s3", "provider-aws-rds", "provider-aws-ec2")


def install_crossplane_provider_aws() -> None:
    """Install the Crossplane AWS family, S3, RDS, and EC2 providers."""
    provider_yaml = "\n---\n".join(
        f"""apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: {name}
spec:
  package: xpkg.upbound.io/upbound/{name}:{AWS_PROVIDER_VERSION}"""
        for name in AWS_PROVIDERS
    )
    run(["kubectl", "apply", "-f", "-"], input=provider_yaml)
    logger.info("aws providers installed, waiting for CRDs")

    for name in AWS_PROVIDERS:
        wait_for_provider_ready(name, timeout=300)


def apply_aws_manifests(project_dir: Path) -> None:
    """Apply Crossplane resources for AWS deployment."""
    infra_dir = project_dir / "infrastructure"

    xrds = infra_dir / "xrds"
    if xrds.is_dir():
        logger.info("applying crossplane xrds")
        run(["kubectl", "apply", "-f", str(xrds)])
        wait_for_crd("buckets.kreator.dev")
        wait_for_crd("databases.kreator.dev")

    provider_configs = infra_dir / "provider-configs"
    if provider_configs.is_dir():
        logger.info("applying provider configs")
        for f in provider_configs.glob("*.yaml"):
            run(["kubectl", "apply", "-f", str(f)], check=False)
        time.sleep(3)

    compositions_dir = infra_dir / "compositions" / "aws"
    if compositions_dir.is_dir():
        logger.info("applying aws compositions")
        run(["kubectl", "apply", "-f", str(compositions_dir)])
        time.sleep(3)

    claims = infra_dir / "claims"
    if claims.is_dir():
        logger.info("applying crossplane claims")
        run(["kubectl", "apply", "-f", str(claims)])


def wait_for_claims_ready(project_dir: Path, timeout: int = 900) -> None:
    """Wait for all Crossplane bucket and database claims to become ready.

    RDS instances take 5-15 minutes to provision, hence the longer timeout.
    """
    claims_dir = project_dir / "infrastructure" / "claims"
    if not claims_dir.is_dir():
        return

    logger.info("waiting for crossplane claims to be ready (this may take several minutes)")
    start = time.time()
    while time.time() - start < timeout:
        all_ready = True
        any_found = False
        for kind in ("buckets.kreator.dev", "databases.kreator.dev"):
            result = run(
                [
                    "kubectl",
                    "get",
                    kind,
                    "-o",
                    "jsonpath={.items[*].status.conditions[?(@.type=='Ready')].status}",
                ],
                capture=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout:
                any_found = True
                if not all(s == "True" for s in result.stdout.split()):
                    all_ready = False
        if any_found and all_ready:
            logger.info("all claims ready")
            return
        time.sleep(10)
    raise RuntimeError(f"Claims not ready after {timeout}s")


def delete_aws_resources(project_dir: Path) -> None:
    """Delete Crossplane claims and compositions for AWS."""
    infra_dir = project_dir / "infrastructure"

    claims = infra_dir / "claims"
    if claims.is_dir():
        logger.info("deleting crossplane claims")
        run(["kubectl", "delete", "-f", str(claims)], check=False)

    compositions_dir = infra_dir / "compositions" / "aws"
    if compositions_dir.is_dir():
        logger.info("deleting aws compositions")
        run(["kubectl", "delete", "-f", str(compositions_dir)], check=False)

    logger.info("waiting for resources to be cleaned up")
    time.sleep(30)
