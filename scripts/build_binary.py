"""Build a native PyInstaller folder bundle and smoke-test its extracted archive."""

import argparse
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

from typesafe_cli import __version__

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        required=True,
        choices=["macos-arm64", "linux-x86_64", "linux-arm64", "windows-x86_64"],
    )
    args = parser.parse_args()
    architecture = {"aarch64": "arm64", "AMD64": "x86_64"}.get(
        platform.machine(), platform.machine()
    )
    os_name = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}[platform.system()]
    assert args.target == f"{os_name}-{architecture}", "Build on the target OS/architecture"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--name",
            "typesafe-cli",
            "--collect-all",
            "typesafe_sdk",
            "--copy-metadata",
            "typesafe-cli",
            str(ROOT / "scripts/entrypoint.py"),
        ],
        cwd=ROOT,
        check=True,
    )
    dist = ROOT / "dist"
    folder = dist / "typesafe-cli"
    shutil.copy2(ROOT / "README.md", folder / "README.md")
    shutil.copy2(ROOT / "CHANGELOG.md", folder / "CHANGELOG.md")
    shutil.copy2(ROOT / "CONTRIBUTING.md", folder / "CONTRIBUTING.md")
    shutil.copytree(
        ROOT / "examples", folder / "examples", ignore=shutil.ignore_patterns("__pycache__")
    )
    stem = f"typesafe-cli-{__version__}-{args.target}"
    archive = Path(
        shutil.make_archive(
            str(dist / stem),
            "zip" if os_name == "windows" else "gztar",
            root_dir=dist,
            base_dir="typesafe-cli",
        )
    )
    with tempfile.TemporaryDirectory() as directory:
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(directory)
        else:
            with tarfile.open(archive) as bundle:
                bundle.extractall(directory, filter="data")
        executable = (
            Path(directory)
            / "typesafe-cli"
            / ("typesafe-cli.exe" if os_name == "windows" else "typesafe-cli")
        )
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/smoke.py"), str(executable), "--binary"],
            check=True,
        )
    print(archive)


if __name__ == "__main__":
    main()
