---
name: typesafe-cli
description: Use typesafe-cli to configure saved API-key authentication, discover TypeSafe models, and run Choice, Score, or Noul evaluations from JSON files or pipelines.
---

# TypeSafe CLI

Compatible with typesafe-cli 0.1.0. Use the installed `typesafe-cli` executable (or
`typesafe-cli.exe` on Windows). Check `--version` and command `--help` before relying on flags.
For installation, updates, platform requirements, and checksums use the
[versioned installation guide](https://github.com/peterbb148/typesafe-cli/blob/v0.1.0/README.md#install).
Standalone bundles support macOS Apple Silicon, Ubuntu x86-64/ARM64, and Windows x86-64;
keep each executable with its `_internal` directory. UV wheel installation is also supported.

## Authentication

Run `typesafe-cli auth status` to inspect local configuration without exposing the key.
`auth login` accepts hidden terminal input and explicitly saves the key in
`~/.config/typesafe-cli/credentials.json` (Windows: `%USERPROFILE%\.config\typesafe-cli\credentials.json`).
For automation, inject `TYPESAFE_API_KEY` through a secret source or explicitly pipe a key to
`auth login --api-key-stdin`; never put keys in command arguments or display them.
A non-empty environment key overrides the saved key without overwriting it.
`auth logout` removes only the saved credential; it neither clears environment overrides nor
revokes the provider key. Status means locally configured, not provider validated.

## Evaluate

1. Use `typesafe-cli models list` to discover accessible models. The default is `jev-latest`;
   use `--model VERSION` for reproducible model selection.
2. Prepare state and a non-empty named question map. Reuse the complete, synthetic
   [mixed question fixture](references/questions.json) and [state fixture](references/state.json),
   or read [question formats and shell examples](references/usage.md) for individual primitives.
3. Run `typesafe-cli evaluate --state state.json --questions questions.json --model jev-1.13.0`.
   State is a JSON string, object, or array. Use `--state -` explicitly for stdin and
   `--state-format text` explicitly for raw UTF-8 text. Malformed JSON is an error.

State and questions are sent to TypeSafe. Use inputs appropriate for that provider.
The CLI emits one complete JSON response, preserving answer IDs, types, actual model, usage,
and any probabilities/confidence present. Noul's `noul` value is its yes probability;
do not invent a separate confidence. Confidence does not prove correctness.

## Pipelines and failures

Success is exit 0 with JSON stdout; invalid input/usage is exit 2; configuration/provider
failure is exit 1. Diagnostics go to stderr, with no partial success JSON. Propagate producer
failures: use Bash `set -o pipefail`, or capture native producer output and check `$LASTEXITCODE`
in PowerShell before handing it to evaluation. See [shell examples](references/usage.md).

Data commands accept `--timeout` (30 seconds by default) and `--retries` (2 by default).
Retries belong to the SDK, with a 60-second retry budget; do not stack unbounded retry loops.
For authentication failures check environment precedence before replacing a stored key.
Do not diagnose failures by printing credentials or private state.

Examples of requests this skill supports: “Save my TypeSafe key”, “List available models”,
“Classify these records and score urgency in one call”, and “Pipe this JSON into TypeSafe”.
Offline tests use mocks; do not describe them as live provider validation.
