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


def install_crossplane_provider_aws() -> None:
    """Install the Crossplane AWS family and S3 providers."""
    provider_yaml = f"""
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-family-aws
spec:
  package: xpkg.upbound.io/upbound/provider-family-aws:{AWS_PROVIDER_VERSION}
---
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-aws-s3
spec:
  package: xpkg.upbound.io/upbound/provider-aws-s3:{AWS_PROVIDER_VERSION}
"""
    run(["kubectl", "apply", "-f", "-"], input=provider_yaml)
    logger.info("aws providers installed, waiting for CRDs")

    wait_for_provider_ready("provider-family-aws", timeout=300)
    wait_for_provider_ready("provider-aws-s3", timeout=300)


def apply_aws_manifests(project_dir: Path) -> None:
    """Apply Crossplane resources for AWS deployment."""
    infra_dir = project_dir / "infrastructure"

    xrds = infra_dir / "xrds"
    if xrds.is_dir():
        logger.info("applying crossplane xrds")
        run(["kubectl", "apply", "-f", str(xrds)])
        wait_for_crd("buckets.kreator.dev")

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

    # Phase 1 provisions S3 only, so apply just the bucket claim. The database
    # claim has no aws composition yet and would sit pending forever.
    claim = infra_dir / "claims" / "bucket.yaml"
    if claim.exists():
        logger.info("applying bucket claim")
        run(["kubectl", "apply", "-f", str(claim)])


def wait_for_claims_ready(project_dir: Path, timeout: int = 600) -> None:
    """Wait for all Crossplane bucket claims to become ready."""
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
                "buckets.kreator.dev",
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


def delete_aws_resources(project_dir: Path) -> None:
    """Delete Crossplane claims and compositions for AWS."""
    infra_dir = project_dir / "infrastructure"

    claim = infra_dir / "claims" / "bucket.yaml"
    if claim.exists():
        logger.info("deleting bucket claim")
        run(["kubectl", "delete", "-f", str(claim)], check=False)

    compositions_dir = infra_dir / "compositions" / "aws"
    if compositions_dir.is_dir():
        logger.info("deleting aws compositions")
        run(["kubectl", "delete", "-f", str(compositions_dir)], check=False)

    logger.info("waiting for resources to be cleaned up")
    time.sleep(30)
