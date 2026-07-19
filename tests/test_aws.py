import re
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from kreator.core.config import KreatorConfig
from kreator.main import app
from kreator.providers.aws import setup_aws_credentials_secret, validate_aws_credentials_file

runner = CliRunner()

FAKE_CREDENTIALS = (
    "[default]\n"
    "aws_access_key_id = AKIAFAKEFAKEFAKEFAKE\n"
    "aws_secret_access_key = fakefakefakefakefakefakefakefakefakefake\n"
)


@pytest.fixture
def run_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def credentials_file(tmp_path: Path) -> Path:
    path = tmp_path / "credentials"
    path.write_text(FAKE_CREDENTIALS)
    return path


# --- config ---


def test_config_accepts_aws_provider() -> None:
    config = KreatorConfig(name="test", provider="aws")
    assert config.provider == "aws"


def test_config_aws_region_default() -> None:
    config = KreatorConfig(name="test", provider="aws")
    assert config.region == "eu-west-1"


def test_config_civo_region_default_unchanged() -> None:
    config = KreatorConfig(name="test", provider="civo")
    assert config.region == "lon1"


def test_config_aws_region_explicit() -> None:
    config = KreatorConfig(name="test", provider="aws", region="us-east-1")
    assert config.region == "us-east-1"


def test_config_aws_region_invalid() -> None:
    with pytest.raises(ValidationError, match="not a valid AWS region"):
        KreatorConfig(name="test", provider="aws", region="lon1")


# --- init ---


def test_init_aws_generates_aws_files(run_in_tmp: Path) -> None:
    result = runner.invoke(app, ["init", "my-app", "--provider", "aws"])
    assert result.exit_code == 0
    base = run_in_tmp / "my-app"
    assert (base / "infrastructure" / "provider-configs" / "aws.yaml").exists()
    assert (base / "infrastructure" / "compositions" / "aws" / "bucket.yaml").exists()
    assert (base / "infrastructure" / "claims" / "bucket.yaml").exists()
    assert (base / "infrastructure" / "xrds" / "bucket.yaml").exists()

    composition = (base / "infrastructure" / "compositions" / "aws" / "bucket.yaml").read_text()
    assert "region: eu-west-1" in composition
    assert "providerConfigRef" in composition
    assert "provider-aws" in composition

    claim = (base / "infrastructure" / "claims" / "bucket.yaml").read_text()
    assert "provider: aws" in claim
    # S3 names are global: the claim must carry a random suffix to avoid collisions.
    assert re.search(r"name: my-app-bucket-[0-9a-f]{8}", claim)


def test_init_civo_omits_aws_files(run_in_tmp: Path) -> None:
    result = runner.invoke(app, ["init", "my-app"])
    assert result.exit_code == 0
    base = run_in_tmp / "my-app"
    assert not (base / "infrastructure" / "provider-configs" / "aws.yaml").exists()
    assert not (base / "infrastructure" / "compositions" / "aws").exists()
    assert not (base / "infrastructure" / "claims" / "bucket.yaml").exists()


# --- credentials file validation ---


def test_validate_credentials_well_formed(credentials_file: Path) -> None:
    validate_aws_credentials_file(credentials_file)


def test_validate_credentials_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        validate_aws_credentials_file(tmp_path / "nonexistent")


def test_validate_credentials_no_default_section(tmp_path: Path) -> None:
    path = tmp_path / "credentials"
    path.write_text("[other]\naws_access_key_id = AKIAFAKEFAKEFAKEFAKE\n")
    with pytest.raises(ValueError, match=r"no \[default\] section"):
        validate_aws_credentials_file(path)


def test_validate_credentials_missing_key(tmp_path: Path) -> None:
    path = tmp_path / "credentials"
    path.write_text("[default]\naws_access_key_id = AKIAFAKEFAKEFAKEFAKE\n")
    with pytest.raises(ValueError, match="aws_secret_access_key"):
        validate_aws_credentials_file(path)


def test_validate_credentials_not_ini(tmp_path: Path) -> None:
    path = tmp_path / "credentials"
    path.write_text("not an ini file at all\n")
    with pytest.raises(ValueError, match="not valid INI"):
        validate_aws_credentials_file(path)


def test_setup_secret_uses_from_file(
    credentials_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        calls.append(cmd)

    monkeypatch.setattr("kreator.providers.aws.run", fake_run)
    setup_aws_credentials_secret(credentials_file)

    create = next(c for c in calls if "create" in c and "secret" in c)
    assert f"--from-file=creds={credentials_file}" in create
    # Key material must never appear in any command argument.
    for cmd in calls:
        assert not any("AKIAFAKE" in arg or "fakefake" in arg for arg in cmd)


def test_setup_secret_rejects_bad_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr("kreator.providers.aws.run", lambda cmd, **kw: calls.append(cmd))
    with pytest.raises(ValueError):
        setup_aws_credentials_secret(tmp_path / "nonexistent")
    assert calls == []


# --- deploy dispatch ---


def _write_project(tmp_path: Path, provider: str) -> None:
    (tmp_path / "kreator.yaml").write_text(
        f"name: my-app\nfrontend: nextjs\nbackend: fastapi\nprovider: {provider}\n"
        "repo_url: https://github.com/me/my-app.git\n"
    )


def test_deploy_dispatches_to_aws(run_in_tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_project(run_in_tmp, "aws")
    called: dict[str, object] = {}
    monkeypatch.setattr(
        "kreator.commands.deploy._deploy_aws",
        lambda config, project_dir, creds: called.update(provider=config.provider, creds=creds),
    )
    result = runner.invoke(app, ["deploy", "--aws-credentials-file", "/tmp/creds"])
    assert result.exit_code == 0
    assert called["provider"] == "aws"
    assert called["creds"] == Path("/tmp/creds")


def test_deploy_dispatches_to_civo(run_in_tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_project(run_in_tmp, "civo")
    called: dict[str, object] = {}
    monkeypatch.setattr(
        "kreator.commands.deploy._deploy_civo",
        lambda config, project_dir, key: called.update(provider=config.provider, key=key),
    )
    result = runner.invoke(app, ["deploy", "--civo-api-key", "fake-key"])
    assert result.exit_code == 0
    assert called["provider"] == "civo"
    assert called["key"] == "fake-key"


def test_deploy_aws_requires_credentials_file(
    run_in_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_project(run_in_tmp, "aws")
    monkeypatch.delenv("AWS_CREDENTIALS_FILE", raising=False)
    result = runner.invoke(app, ["deploy"])
    assert result.exit_code == 1
    assert "AWS credentials file required" in result.output
