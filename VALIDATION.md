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

The committed CI matrix builds and smoke-tests macOS ARM64, Ubuntu ARM64/x86-64, and Windows
x86-64 artifacts on matching native runners. At the time of this record, remote CI/publication
is pending GitHub workflow-scope authorization; no macOS, ARM64, or Windows success is claimed.
