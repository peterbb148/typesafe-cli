# typesafe-cli

Compose [TypeSafe AI](https://docs.typesafe.ai/sdk/python) evaluations through JSON.
Save an API key once, discover models, and evaluate Choice, Score, and Noul questions together.

## Install

Download versioned assets and `SHA256SUMS` from [GitHub Releases](https://github.com/peterbb148/typesafe-cli/releases).
The standalone folder bundles include Python; keep the executable beside its `_internal` directory.

| Asset suffix | Supported baseline | Native CI runner |
| --- | --- | --- |
| `macos-arm64.tar.gz` | macOS 14+, Apple Silicon | macOS 14 ARM64 |
| `linux-x86_64.tar.gz` | Ubuntu 24.04+, glibc 2.39+, x86-64 | Ubuntu 24.04 |
| `linux-arm64.tar.gz` | Ubuntu 24.04+, glibc 2.39+, ARM64 | Ubuntu 24.04 ARM64 |
| `windows-x86_64.zip` | Windows Server 2022 / Windows 11+, x86-64 | Windows Server 2022 |

Windows 11 compatibility is expected from the shared runtime; the automated native smoke test runs on Server 2022.
The macOS bundle has ad-hoc signing only, without Apple notarization. Windows binaries have no Authenticode signature.
Operating-system download protections may require manual approval for these unsigned/unnotarized downloads.
No PyPI package or system package manager distribution is provided in this release.

Bash, after downloading the matching archive and checksum file:

```bash
# Linux; on macOS use: shasum -a 256 <archive>
sha256sum typesafe-cli-0.1.0-linux-x86_64.tar.gz
# Compare with the matching line in SHA256SUMS before extracting.
mkdir -p "$HOME/.local/lib/typesafe-cli-0.1.0" "$HOME/.local/bin"
tar -xzf typesafe-cli-0.1.0-linux-x86_64.tar.gz -C "$HOME/.local/lib/typesafe-cli-0.1.0"
ln -sfn "$HOME/.local/lib/typesafe-cli-0.1.0/typesafe-cli/typesafe-cli" "$HOME/.local/bin/typesafe-cli"
export PATH="$HOME/.local/bin:$PATH"
typesafe-cli --version
```

PowerShell:

```powershell
Get-FileHash .\typesafe-cli-0.1.0-windows-x86_64.zip -Algorithm SHA256
# Compare with the matching line in SHA256SUMS before extracting.
Expand-Archive .\typesafe-cli-0.1.0-windows-x86_64.zip "$HOME\Apps\typesafe-cli-0.1.0"
$env:PATH = "$HOME\Apps\typesafe-cli-0.1.0\typesafe-cli;" + $env:PATH
typesafe-cli --version
```

Persist your chosen PATH addition using your shell profile or Windows user environment settings.
To upgrade, extract a new version into its own folder and update the symlink/PATH. To uninstall,
remove that link/PATH entry and installation folder. Run `auth logout` first if you also want to
remove saved credentials; deleting the executable alone does not remove them.

Alternatively, with UV and Python 3.12–3.14:

```bash
uv tool install https://github.com/peterbb148/typesafe-cli/releases/download/v0.1.0/typesafe_cli-0.1.0-py3-none-any.whl
# Upgrade by repeating with the new version's wheel URL and --force.
uv tool uninstall typesafe-cli
```

## Authenticate once

Create a key in the [TypeSafe console](https://console.typesafe.ai), then run:

```bash
typesafe-cli auth login
typesafe-cli auth status
typesafe-cli models list
```

`auth login` prompts with hidden input and stores the key in
`~/.config/typesafe-cli/credentials.json`, including on macOS. On Windows this is
`%USERPROFILE%\.config\typesafe-cli\credentials.json`. The file is locally stored plaintext,
protected with owner-only permissions (0700 directory/0600 file on Unix; user-only protected ACLs
on Windows). Writes are atomic. No key values appear in CLI output.

`auth status` checks local configuration, **not provider validity**; `models list` makes an
actual authenticated request. `auth logout` removes the saved key, preserves other settings,
and does not revoke the provider key or clear the calling shell's environment.

A non-empty `TYPESAFE_API_KEY` overrides the saved key for that invocation without modifying it.
For automation, inject this variable through your secret manager, or pipe a key from a secret
source to `typesafe-cli auth login --api-key-stdin`. Do not put a key in command-line arguments.
Data commands never prompt for credentials or consume evaluation stdin as a key.

## Evaluate

Use the bundled [examples](examples) or create these files:

`state.json`:
```json
{"document":"I was charged twice. Please fix this today."}
```

`questions.json`:
```json
{
  "billing": {"type":"noul","instructions":"Is this about billing?"},
  "tone": {"type":"choice","instructions":"What is the tone?","criteria":{"calm":null,"frustrated":null}},
  "urgency": {"type":"score","instructions":"How urgent is this?","criteria":["can wait","this week","today"]}
}
```

```bash
typesafe-cli evaluate --state state.json --questions questions.json --model jev-1.13.0
set -o pipefail
cat state.json | typesafe-cli evaluate --state - --questions questions.json
printf '%s' 'Please help today' | typesafe-cli evaluate --state - --state-format text --questions questions.json
```

PowerShell (use UTF-8 for piped non-ASCII text):

```powershell
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Get-Content -Raw state.json | typesafe-cli evaluate --state - --questions questions.json
if ($LASTEXITCODE -ne 0) { throw 'TypeSafe evaluation failed' }
# For native producers, capture and check their exit code before passing data onwards:
$state = producer --json
if ($LASTEXITCODE -ne 0) { throw 'Producer failed' }
$state | typesafe-cli evaluate --state - --questions questions.json
if ($LASTEXITCODE -ne 0) { throw 'TypeSafe evaluation failed' }
```

JSON state must be a string, object, or array; it is never double encoded. Malformed JSON is an
error; raw text requires `--state-format text`. Question definitions are a non-empty named map
using the official SDK's validation contract. Instructions and criteria may contain structured
JSON where supported; unknown fields and invalid definitions fail before network access.
See [individual Choice](examples/choice.json), [Score](examples/score.json), and
[Noul](examples/noul.json) fixtures, plus [mixed questions](examples/questions.json).

The default model is `jev-latest`; `--model` pins an explicit version. Use `models list` to see
available versions. State and questions are sent to TypeSafe; bundled examples are synthetic.

## Command and output contract

| Command | Result |
| --- | --- |
| `--help`, `--version` | Local help/version, no credentials or network |
| `auth login [--api-key-stdin]` | Saves a key; JSON reports success without revealing it |
| `auth status` | JSON configured/source/provider_validated fields |
| `auth logout` | JSON removal/environment-override status |
| `models list [--timeout SECONDS] [--retries N]` | Complete provider model-list JSON |
| `evaluate --state PATH\|- --questions PATH [--state-format json\|text] [--model MODEL]` | Complete provider evaluation JSON |

Successful data commands emit one JSON document plus a newline. Diagnostics and prompts go to
stderr. Exit codes: **0** success, **2** invalid input/usage, **1** configuration/provider failure.
No partial success JSON is emitted on failure. Evaluation responses retain question IDs, typed
answers, actual model, usage, probabilities/confidence, and additional provider JSON fields.
Noul returns its `noul` probability; the CLI never manufactures confidence. Confidence is not
proof of correctness or a calibrated guarantee for your application.

Both data commands support `--timeout` (default 30 seconds, range 0.001–300) and `--retries`
(default 2, range 0–5). The official SDK retries transient failures with backoff, respecting its
60-second retry budget; this budget prevents scheduling more retries and is not a hard wall-clock
deadline for an in-flight request. There is no additional CLI retry loop. SDK request-body logging
is disabled in the CLI, including when `TYPESAFE_LOG_LEVEL` is set.

`TYPESAFE_BASE_URL` is an advanced SDK endpoint override, used by offline tests; it sends your
key and state to the selected server, so use only an endpoint you intend to trust.

If authentication fails, check `auth status` and whether an environment key overrides the file.
For permission failures, repair the private config directory or run `auth login`. For malformed
credentials, replace them with `auth login`. Provider failures return sanitized errors; check
network, model access, account limits, or service status as indicated. No automatic credential
refresh or persistent request logging is performed.

## Gitomics and Codex skill

The [optional Gitomics example](examples/gitomics/README.md) adapts discovery JSON into questions,
validates exact dataset IDs, and only performs a read when requested. Gitomics is not a dependency.

Download `typesafe-cli-0.1.0-skill.zip` from the same release and extract its `typesafe-cli` folder
into `~/.codex/skills/` (or your configured `$CODEX_HOME/skills`). The result should contain
`~/.codex/skills/typesafe-cli/SKILL.md`. On Windows use the same path beneath your user home.
The portable folder includes its examples/references. Invoke `$typesafe-cli` or ask naturally:
“Use typesafe-cli to evaluate these records against a Choice and a Score question.”
Update the skill alongside the CLI.

## Development and validation

See [CONTRIBUTING](CONTRIBUTING.md). CI validates Python 3.12–3.14, builds each native bundle on
its target platform, and runs the extracted artifact against a mock server from a temporary home
with Python/UV absent from PATH. Tagging a matching `vVERSION` publishes only after those checks.
Mock tests establish CLI behavior, not live provider correctness. The separately invoked live
smoke test requires an explicitly supplied key and sends only the synthetic mixed fixture:

```bash
uv run python scripts/live_smoke.py
```
