# Contributing

Use Python 3.12–3.14 and UV 0.9.22 (the CI version).

```bash
uv sync --frozen
uv run typesafe-cli --help
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv build
uv run python scripts/smoke_wheel.py
uv run python scripts/build_binary.py --target linux-x86_64
```

Choose the binary target matching the build host: `linux-x86_64`, `linux-arm64`, `macos-arm64`,
or `windows-x86_64`. Build Linux release artifacts on Ubuntu 24.04, macOS on 14, Windows on
Server 2022. Do not cross-label an artifact from another host. PyInstaller is pinned in the
UV lockfile. Complete build and smoke checks use fake keys and temporary home directories.

The package separates command definitions (`cli.py`), credential storage (`auth.py`), input/output
(`io.py`), and SDK calls/error handling (`adapter.py`). Gitomics stays in `examples/` and never
enters core dependencies. Tests use real SDK parsing with mock transport or a local mock server.

`src/typesafe_cli/__init__.py` is the single package/binary version source. Change its version,
update docs/skill/changelog, regenerate `uv.lock`, run checks, and tag `vVERSION`. The tag workflow
runs the full native matrix, then attaches Python distributions, binary archives, portable skill,
and SHA256SUMS. Binary builds are repeatable from pinned inputs but OS runner images and archive
timestamps mean byte-identical native artifacts are not promised. Hatchling produces reproducible
Python distributions from the same source and build inputs.

Never add credentials or private evaluation inputs to fixtures. Live validation is opt-in:
explicitly supply `TYPESAFE_API_KEY` and run `uv run python scripts/live_smoke.py`. Record live and
mock evidence separately.
