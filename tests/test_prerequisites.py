import subprocess
from unittest.mock import patch

from kreator.core.platform import check_prerequisites, wait_for_db_ready


class TestCheckPrerequisites:
    def test_all_tools_present(self):
        with patch("kreator.core.platform.shutil.which", return_value="/usr/bin/tool"):
            with patch("kreator.core.platform.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess([], 0)
                errors = check_prerequisites()
        assert errors == []

    def test_missing_tool(self):
        def which_side_effect(name):
            if name == "kind":
                return None
            return f"/usr/bin/{name}"

        with patch("kreator.core.platform.shutil.which", side_effect=which_side_effect):
            with patch("kreator.core.platform.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess([], 0)
                errors = check_prerequisites()
        assert len(errors) == 1
        assert "kind" in errors[0]

    def test_docker_not_running(self):
        with patch("kreator.core.platform.shutil.which", return_value="/usr/bin/tool"):
            with patch("kreator.core.platform.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess([], 1)
                errors = check_prerequisites()
        assert len(errors) == 1
        assert "Docker daemon" in errors[0]

    def test_multiple_missing(self):
        def which_side_effect(name):
            if name in ("kind", "helm"):
                return None
            return f"/usr/bin/{name}"

        with patch("kreator.core.platform.shutil.which", side_effect=which_side_effect):
            with patch("kreator.core.platform.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess([], 0)
                errors = check_prerequisites()
        assert len(errors) == 2
        assert any("kind" in e for e in errors)
        assert any("helm" in e for e in errors)


class TestWaitForDbReady:
    def test_uses_dynamic_name(self):
        with patch("kreator.core.platform.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="1", stderr="")
            wait_for_db_ready("my-project", timeout=5)

        call_args = mock_run.call_args_list[0]
        cmd = call_args[0][0]
        assert "my-project-db" in cmd

    def test_different_project_name(self):
        with patch("kreator.core.platform.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="1", stderr="")
            wait_for_db_ready("cool-app", timeout=5)

        call_args = mock_run.call_args_list[0]
        cmd = call_args[0][0]
        assert "cool-app-db" in cmd
