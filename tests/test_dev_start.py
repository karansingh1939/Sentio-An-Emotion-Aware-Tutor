"""The launcher must work without activating the project environment."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


def test_launcher_uses_project_python_and_propagates_failure(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("dev_start", root / "scripts/dev_start.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    run = Mock(return_value=SimpleNamespace(returncode=7))
    monkeypatch.setattr(launcher.subprocess, "run", run)
    monkeypatch.setattr(launcher.sys, "argv", ["dev_start.py", "--port", "8001"])
    assert launcher.main() == 7
    command = run.call_args.args[0]
    assert Path(command[0]).is_relative_to(root / ".venv")
    assert command[1:] == ["-m", "sentio", "--port", "8001"]


def test_environment_checker_detects_missing_current_dependency(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "check_environment", root / "scripts/check_environment.py"
    )
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)

    def installed_version(package):
        if package == "fastapi":
            raise checker.PackageNotFoundError(package)
        return "1.0"

    monkeypatch.setattr(checker, "version", installed_version)
    assert checker.check_dependencies() is False
