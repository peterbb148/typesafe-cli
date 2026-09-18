"""Explicit live check: sends the bundled synthetic state to TypeSafe and may incur usage."""

import json
import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if not os.environ.get("TYPESAFE_API_KEY", "").strip():
    raise SystemExit("Supply TYPESAFE_API_KEY explicitly for this live smoke test.")
for args in (
    ["models", "list"],
    [
        "evaluate",
        "--state",
        str(root / "examples/state.json"),
        "--questions",
        str(root / "examples/questions.json"),
    ],
):
    result = subprocess.run(["typesafe-cli", *args], capture_output=True, text=True, check=True)
    value = json.loads(result.stdout)
    assert isinstance(value, dict)
print("Live model discovery and mixed evaluation passed.")
