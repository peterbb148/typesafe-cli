# Question files and shell usage

The companion JSON fixtures are runnable with typesafe-cli 0.1.0. Use the path where this
skill is installed, or copy them into your working directory. Individual fixtures:
[Choice](choice.json), [Score](score.json), [Noul](noul.json), [mixed](questions.json), [state](state.json).

Question files are a map from stable answer IDs to definitions, each with `type` equal to
`choice`, `score`, or `noul`. Choice criteria map labels to descriptions or null. Score criteria
are ordered descriptions. Noul optionally accepts `criteria` with `true` and `false` descriptions.
Instructions and descriptions support structured JSON under the official SDK contract; for
example the mixed fixture includes an object instruction and object-valued Choice description.
Do not flatten or double-encode them. Unknown fields and empty Choice/Score criteria fail locally.

Bash, from a directory containing the copied fixtures:

```bash
set -o pipefail
typesafe-cli evaluate --state state.json --questions choice.json
typesafe-cli evaluate --state state.json --questions score.json
typesafe-cli evaluate --state state.json --questions noul.json
cat state.json | typesafe-cli evaluate --state - --questions questions.json --model jev-1.13.0
printf '%s' 'Charged twice today' | typesafe-cli evaluate --state - --state-format text --questions questions.json
```

PowerShell:

```powershell
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
typesafe-cli evaluate --state state.json --questions questions.json
if ($LASTEXITCODE -ne 0) { throw 'Evaluation failed' }
$state = producer --json
if ($LASTEXITCODE -ne 0) { throw 'Producer failed' }
$state | typesafe-cli evaluate --state - --questions questions.json
if ($LASTEXITCODE -ne 0) { throw 'Evaluation failed' }
```

A Choice answer contains `type`, `choice`, `probabilities`, and `confidence`. Score additionally
uses `score` and `legend`; Noul uses `noul`. All appear under `answers.<question-id>` alongside
response `model` and `usage`. Preserve additional provider metadata when processing responses.
