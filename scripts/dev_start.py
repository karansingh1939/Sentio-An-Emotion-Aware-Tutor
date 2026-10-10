#!/usr/bin/env python
"""Launch Sentio using the project environment, without manual activation."""

import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def main():
    project_python = (
        BASE_DIR / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    )
    if project_python.is_file():
        command = [str(project_python), "-m", "sentio"]
    elif shutil.which("uv"):
        command = ["uv", "run", "--project", str(BASE_DIR), "sentio"]
    else:
        print(
            "Set up the project first: install uv, then run uv sync in the project folder.",
            file=sys.stderr,
        )
        return 1
    command.extend(sys.argv[1:])
    print("Launching: " + " ".join(command), flush=True)
    try:
        return subprocess.run(command, cwd=BASE_DIR).returncode
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
