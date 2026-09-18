# Validation evidence

## Local validation — 2026-09-18

- 51 tests passed independently on Python 3.12, 3.13, and 3.14 on Ubuntu 24.04 x86-64.
- Ruff lint and formatting checks passed; the portable skill validator passed.
- Wheel installation outside the checkout passed the mock-provider artifact smoke test.
- The extracted Ubuntu x86-64 binary passed authentication, model discovery, file/stdin/text
  evaluations, and failure-contract checks with Python/UV absent from PATH and a temporary home.
- Two builds from the same source produced matching wheel and sdist SHA-256 hashes.

## Live provider validation — 2026-09-18

The standalone Ubuntu x86-64 binary used a user-supplied key saved through `auth login`.
No credentials are included in the repository or this record.

- `typesafe-cli models list` succeeded against TypeSafe and returned model metadata.
- `typesafe-cli evaluate --state examples/state.json --questions examples/questions.json
  --model jev-1.13.0` succeeded using the bundled synthetic billing fixture.
- The response reported model `jev-1.13.0`, all three named typed answers, probabilities and
  confidence where applicable, and usage of 383 input tokens / 67 output tokens.
- This was a real provider call, separate from mock tests. It does not establish correctness
  or confidence calibration for other inputs. Gitomics integration remains offline-tested.

## Cross-platform release validation

[CI run 35349424847](https://github.com/peterbb148/typesafe-cli/actions/runs/35349424847)
passed on commit `039ebd7`:

- Ubuntu 24.04 x86-64 and ARM64: native binary builds and extracted-archive smoke tests passed.
- macOS 14 Apple Silicon ARM64: native binary build and extracted-archive smoke test passed.
- Windows Server 2022 x86-64: native binary build and extracted-archive smoke test passed,
  including verification that stored credential ACL entries grant access only to the current user.
- Python 3.12, 3.13, and 3.14 checks passed. Each platform ran 51 tests with one platform-specific
  permission test skipped (POSIX mode checks on Windows; Windows ACL checks on Unix).
- Each wheel was installed outside the checkout and exercised against a mock provider.

The first Windows run exposed default-encoding assumptions in test fixtures; these were fixed
with explicit UTF-8. The installed-wheel check also assumed a single ACL entry; it now verifies
all entries belong to the current user and that inheritance is protected.

The tag-triggered release workflow repeats the full matrix before publishing all seven artifacts
plus SHA256SUMS. Consult the release workflow run for validation of the exact tagged source.
