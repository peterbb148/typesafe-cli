"""Create the portable skill bundle and checksums over release artifacts."""

import argparse
import hashlib
import shutil
from pathlib import Path

from typesafe_cli import __version__

parser = argparse.ArgumentParser()
parser.add_argument("--require-all", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
dist = root / "dist"
dist.mkdir(exist_ok=True)
shutil.make_archive(
    str(dist / f"typesafe-cli-{__version__}-skill"), "zip", root / "skills", "typesafe-cli"
)
expected = {
    f"typesafe-cli-{__version__}-{target}.{extension}"
    for target, extension in (
        ("macos-arm64", "tar.gz"),
        ("linux-x86_64", "tar.gz"),
        ("linux-arm64", "tar.gz"),
        ("windows-x86_64", "zip"),
        ("skill", "zip"),
    )
} | {f"typesafe_cli-{__version__}-py3-none-any.whl", f"typesafe_cli-{__version__}.tar.gz"}
if args.require_all:
    missing = expected - {p.name for p in dist.iterdir()}
    if missing:
        raise SystemExit("Missing required release artifacts: " + ", ".join(sorted(missing)))
artifacts = sorted(p for p in dist.iterdir() if p.is_file() and p.name in expected)
(dist / "SHA256SUMS").write_text(
    "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in artifacts)
)
