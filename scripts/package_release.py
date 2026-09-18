"""Create the portable skill bundle and checksums over all release artifacts."""

import hashlib
import shutil
from pathlib import Path

from typesafe_cli import __version__

root = Path(__file__).resolve().parents[1]
dist = root / "dist"
dist.mkdir(exist_ok=True)
shutil.make_archive(
    str(dist / f"typesafe-cli-{__version__}-skill"), "zip", root / "skills", "typesafe-cli"
)
artifacts = sorted(p for p in dist.iterdir() if p.is_file() and p.name != "SHA256SUMS")
(dist / "SHA256SUMS").write_text(
    "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in artifacts)
)
