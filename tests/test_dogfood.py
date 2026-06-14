"""Regression guards for issues found while dogfooding kreator on real projects.

Each test pins an invariant that silently broke a generated project once (see
ISSUES.md). These run against freshly generated output so a template change can't
quietly reintroduce the same bug.
"""

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from kreator.main import app

runner = CliRunner()

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Generate a default project and return its directory."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "demo"])
    assert result.exit_code == 0, result.output
    return tmp_path / "demo"


def _statefulset(composition_path: Path) -> dict:
    """Return the postgres StatefulSet manifest from a local database composition."""
    comp = yaml.safe_load(composition_path.read_text())
    for resource in comp["spec"]["resources"]:
        if resource["name"] == "postgres-statefulset":
            return resource["base"]["spec"]["forProvider"]["manifest"]
    raise AssertionError("postgres-statefulset resource not found")


def test_nextjs_static_is_writable_by_runtime_user(project: Path) -> None:
    """Issue #1: static files must be owned by the runtime user so the entrypoint
    can rewrite the baked API URL; otherwise the browser falls back to port 80."""
    dockerfile = (project / "apps" / "frontend" / "Dockerfile").read_text()
    assert "COPY --chown=1001:1001 --from=builder /build/.next/static" in dockerfile


def test_local_postgres_has_persistent_volume(project: Path) -> None:
    """Issue #2: the local postgres StatefulSet must persist PGDATA on a PVC so a
    pod restart does not wipe the database."""
    sts = _statefulset(project / "infrastructure" / "compositions" / "local" / "database.yaml")
    spec = sts["spec"]

    assert spec.get("volumeClaimTemplates"), "missing volumeClaimTemplates"
    claim = spec["volumeClaimTemplates"][0]

    container = spec["template"]["spec"]["containers"][0]
    mounts = {m["name"]: m["mountPath"] for m in container.get("volumeMounts", [])}
    assert mounts.get(claim["metadata"]["name"]) == "/var/lib/postgresql/data"

    # PGDATA must live in a subdir of the mount, not the mount root.
    pgdata = next((e for e in container.get("env", []) if e["name"] == "PGDATA"), None)
    assert pgdata is not None, "PGDATA env not set"
    assert pgdata["value"].startswith("/var/lib/postgresql/data/")


def test_helm_values_expose_image_tag(project: Path) -> None:
    """Auto-roll: every web workload must expose image.tag so kreator dev can pin
    it to an immutable SHA and ArgoCD rolls the pods on a rebuild."""
    for chart in ("backend", "frontend"):
        chart_dir = project / "deploy" / "helm" / chart
        values = yaml.safe_load((chart_dir / "values.yaml").read_text())
        assert "tag" in values["image"], f"{chart} values.yaml has no image.tag"
        deployment = (chart_dir / "templates" / "deployment.yaml").read_text()
        assert ".Values.image.tag" in deployment


def test_argocd_apps_track_head(project: Path) -> None:
    """Clean-git: the in-cluster git server serves the local-dev branch as HEAD,
    so the ArgoCD apps must target HEAD for that to take effect."""
    argocd_dir = project / "deploy" / "argocd"
    for app_file in argocd_dir.rglob("*.yaml"):
        doc = yaml.safe_load(app_file.read_text())
        source = doc.get("spec", {}).get("source", {})
        if "targetRevision" in source:
            assert source["targetRevision"] == "HEAD", f"{app_file.name} does not track HEAD"


def test_readme_does_not_hardcode_dev_port() -> None:
    """Issue #5: per-project clusters assign different host ports, so the README
    must not hardcode a single one."""
    readme = (REPO_ROOT / "README.md").read_text()
    assert ":9080" not in readme
