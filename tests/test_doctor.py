import subprocess
from unittest.mock import patch

from typer.testing import CliRunner

from kreator.main import app

runner = CliRunner()


def _fake_run(cmd, capture=False, check=True, input=None):
    text = " ".join(cmd)
    stdout = ""
    if "get clusters" in text:
        stdout = "kreator-dev"
    elif "get nodes" in text:
        stdout = "True True True"
    elif "helm status" in text:
        pass
    elif "get deployment" in text:
        stdout = "1"
    elif "get crd databases" in text:
        pass
    elif "get compositions" in text:
        stdout = "local-database"
    elif "databases.kreator.dev/testapp-db" in text:
        stdout = "database.kreator.dev/testapp-db"
    elif "get statefulset" in text:
        stdout = "1"
    elif "app.kubernetes.io/name" in text:
        stdout = "true"
    elif "docker info" in text:
        pass
    return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")


class TestDoctor:
    def test_all_passing(self, tmp_path):
        config = tmp_path / "kreator.yaml"
        config.write_text(
            "name: testapp\nfrontend: nextjs\nbackend: fastapi\n"
            "database: postgres\nprovider: civo\nregion: lon1\n"
        )

        with patch("kreator.commands.doctor.run", side_effect=_fake_run):
            with patch("kreator.core.platform.shutil.which", return_value="/usr/bin/tool"):
                with patch("kreator.core.platform.run") as mock_plat_run:
                    mock_plat_run.return_value = subprocess.CompletedProcess([], 0)
                    with patch("pathlib.Path.cwd", return_value=tmp_path):
                        result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 0
        assert "[ok]" in result.output
        assert "[!!]" not in result.output

    def test_no_project_dir(self, tmp_path):
        with patch("kreator.core.platform.shutil.which", return_value="/usr/bin/tool"):
            with patch("kreator.core.platform.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess([], 0)
                with patch("pathlib.Path.cwd", return_value=tmp_path):
                    result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 0
        assert "Not in a kreator project directory" in result.output

    def test_missing_prerequisite(self, tmp_path):
        def which_side_effect(name):
            if name == "helm":
                return None
            return f"/usr/bin/{name}"

        with patch("kreator.core.platform.shutil.which", side_effect=which_side_effect):
            with patch("kreator.core.platform.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess([], 0)
                with patch("pathlib.Path.cwd", return_value=tmp_path):
                    result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 0
        assert "[!!]" in result.output
        assert "helm" in result.output
