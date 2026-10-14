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
(`io.py`), and SDK calls/error handling (`adapter.py`). Examples demonstrate generic TypeSafe
inputs and JSON pipelines. Tests use real SDK parsing with mock transport or a local mock server.

`src/typesafe_cli/__init__.py` is the single package/binary version source. Change its version,
update docs/skill/changelog, regenerate `uv.lock`, run checks, and tag `vVERSION`. The tag workflow
runs the full native matrix, then attaches Python distributions, binary archives, portable skill,
and SHA256SUMS. Binary builds are repeatable from pinned inputs but OS runner images and archive
timestamps mean byte-identical native artifacts are not promised. Hatchling produces reproducible
Python distributions from the same source and build inputs.

Actions artifact retention keeps the two newest successful builds with unexpired artifacts,
across CI (including pull requests) and Release combined, ordered by run creation time. Each
build's four native bundles and Python distributions are retained together. These are build
runs, not distinct package versions; several builds can share a version. After either workflow
succeeds, the separate Artifact retention workflow deletes matching artifacts from other
completed CI/Release runs, including failed or cancelled builds. Queued/running builds are
protected, so storage can temporarily exceed two sets. Release validation artifacts remain
protected until the entire Release run, including publication, finishes. GitHub's configured
artifact expiration still applies to retained builds. Published GitHub Release assets are
unaffected.

The cleanup uses trusted default-branch code and only its job receives `actions: write`.
It becomes active after the workflow is merged to the default branch and a CI or Release run
succeeds. Preview the same policy without deleting anything using authenticated `gh`:

```bash
uv run --no-project python scripts/prune_artifacts.py --repo peterbb148/typesafe-cli
```

Add `--apply` to delete the selected artifacts. API failures stop cleanup and fail the job.

Never add credentials or private evaluation inputs to fixtures. Live validation is opt-in:
explicitly supply `TYPESAFE_API_KEY` and run `uv run python scripts/live_smoke.py`. Record live and
mock evidence separately.
