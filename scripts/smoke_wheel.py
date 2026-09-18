"""Install the wheel without the checkout on sys.path, then test the installed command."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
wheel = next((root / "dist").glob("*.whl"))
with tempfile.TemporaryDirectory() as directory:
    environment = Path(directory) / "venv"
    subprocess.run(["uv", "venv", str(environment), "--python", sys.executable], check=True)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(["uv", "pip", "install", "--python", str(python), str(wheel)], check=True)
    executable = environment / (
        "Scripts/typesafe-cli.exe" if os.name == "nt" else "bin/typesafe-cli"
    )
    subprocess.run([sys.executable, str(root / "scripts/smoke.py"), str(executable)], check=True)
