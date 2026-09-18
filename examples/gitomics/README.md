# Gitomics dataset selection example

Requires Python 3.12+ for the adapter, the TypeSafe CLI, and optionally a separately installed
Gitomics CLI. `discovery.json` contains synthetic records shaped like Gitomics `records` with
exact `id` values. No live Gitomics data is bundled. Only compact IDs, names, genome, and tags
are sent as state. Real state/questions are sent to TypeSafe; choose appropriate records.

Prepare inspectable state/questions using a scientist's explicit question:

```bash
python examples/gitomics/adapter.py prepare --discovery examples/gitomics/discovery.json --question 'Which dataset can support a barley genotype comparison?' --output /tmp/typesafe-example
cat /tmp/typesafe-example/state.json
cat /tmp/typesafe-example/questions.json
typesafe-cli evaluate --state /tmp/typesafe-example/state.json --questions /tmp/typesafe-example/questions.json --model jev-1.13.0 > /tmp/typesafe-example/answer.json
# Only continue if evaluation succeeded.
python examples/gitomics/adapter.py select --discovery examples/gitomics/discovery.json --response /tmp/typesafe-example/answer.json
```

For live discovery, preserve the producer exit status before preparing any request:

```bash
set -euo pipefail
gitomics-cli datasets list --json > discovery.json
python examples/gitomics/adapter.py prepare --discovery discovery.json --question 'Which dataset can support a barley genotype comparison?' --output request
typesafe-cli evaluate --state request/state.json --questions request/questions.json > answer.json
python examples/gitomics/adapter.py select --discovery discovery.json --response answer.json --threshold 0.8
# Opt-in read, using the validated exact ID from the same candidate list:
python examples/gitomics/adapter.py select --discovery discovery.json --response answer.json --threshold 0.8 --read
```

PowerShell: after **each native command**, check `$LASTEXITCODE` before running the next:

```powershell
$discovery = gitomics-cli datasets list --json
if ($LASTEXITCODE -ne 0) { throw 'Discovery failed' }
[System.IO.File]::WriteAllText("$PWD/discovery.json", ($discovery -join "`n"), [System.Text.UTF8Encoding]::new($false))
# Use the same file-based prepare/evaluate/select commands, checking each exit code.
```

The adapter only executes the fixed argument array `gitomics-cli datasets show <validated-id> --json`
with shell execution disabled. TypeSafe answer JSON is not a Gitomics argument contract: the
adapter checks membership and uncertainty before constructing that read. Unknown IDs fail;
`unsupported`, `needs_clarification`, missing/invalid confidence, or confidence below the threshold
perform no read. The 0.8 threshold is illustrative and configurable, not a calibrated guarantee.

`uv run pytest tests/test_gitomics.py -q` exercises the pipeline offline with mocked provider and
Gitomics output, including invented IDs, uncertainty, and provider failure. Live use is optional
and has not been established by those mocks.
