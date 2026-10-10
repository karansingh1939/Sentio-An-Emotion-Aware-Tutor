"""Run the complete pytest suite, forwarding optional pytest arguments."""

import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    return subprocess.call([sys.executable, "-m", "pytest", *sys.argv[1:]], cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())
