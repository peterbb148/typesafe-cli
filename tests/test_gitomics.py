import importlib.util
import json
import subprocess
from pathlib import Path

import httpx2
import pytest
from typer.testing import CliRunner
from typesafe_sdk import TypeSafeClient

from typesafe_cli import adapter as provider
from typesafe_cli.cli import app

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "gitomics_example", ROOT / "examples/gitomics/adapter.py"
)
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)


def discovery():
    return json.loads((ROOT / "examples/gitomics/discovery.json").read_text())


@pytest.mark.parametrize(
    "selected,confidence,outcome",
    [
        ("synthetic-barley-001", 0.95, "selected"),
        ("synthetic-barley-001", 0.3, "needs_clarification"),
        ("unsupported", 0.95, "unsupported"),
        ("needs_clarification", 0.95, "needs_clarification"),
    ],
)
def test_offline_pipeline(tmp_path, monkeypatch, selected, confidence, outcome):
    data = discovery()
    example.prepare(data, "Which dataset supports barley genotype comparison?", tmp_path)

    def request(req):
        sent = json.loads(req.content)
        assert set(sent["questions"]["dataset"]["criteria"]) == {
            "synthetic-barley-001",
            "synthetic-yeast-001",
            "unsupported",
            "needs_clarification",
        }
        return httpx2.Response(
            200,
            json={
                "model": "jev-test",
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "answers": {
                    "dataset": {
                        "type": "choice",
                        "choice": selected,
                        "probabilities": {selected: 1.0},
                        "confidence": confidence,
                    }
                },
            },
        )

    monkeypatch.setenv("TYPESAFE_API_KEY", "fake")
    monkeypatch.setattr(
        provider.sdk,
        "TypeSafeClient",
        lambda **kw: TypeSafeClient(**kw, transport=httpx2.MockTransport(request)),
    )
    result = CliRunner().invoke(
        app,
        [
            "evaluate",
            "--state",
            str(tmp_path / "state.json"),
            "--questions",
            str(tmp_path / "questions.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        assert kwargs["shell"] is False and kwargs["check"] is True
        return subprocess.CompletedProcess(args, 0, json.dumps({"id": selected}), "")

    monkeypatch.setattr(example.subprocess, "run", run)
    value = example.select(data, json.loads(result.stdout), read=True)
    assert value["outcome"] == outcome
    assert len(calls) == (1 if outcome == "selected" else 0)
    if calls:
        assert calls[0] == ["gitomics-cli", "datasets", "show", selected, "--json"]


@pytest.mark.parametrize("selected", ["invented", "--help", "x; rm -rf /"])
def test_invented_id_never_read(monkeypatch, selected):
    def forbidden(*a, **kw):
        pytest.fail("Must not read an unvalidated ID")

    monkeypatch.setattr(example.subprocess, "run", forbidden)
    with pytest.raises(ValueError):
        example.select(
            discovery(),
            {"answers": {"dataset": {"type": "choice", "choice": selected, "confidence": 1}}},
            read=True,
        )


def test_provider_failure_stops_pipeline(tmp_path, monkeypatch):
    example.prepare(discovery(), "Barley?", tmp_path)
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake")
    monkeypatch.setattr(
        provider.sdk,
        "TypeSafeClient",
        lambda **kw: TypeSafeClient(
            **kw,
            transport=httpx2.MockTransport(
                lambda r: httpx2.Response(500, json={"error": "failure"})
            ),
        ),
    )
    result = CliRunner().invoke(
        app,
        [
            "evaluate",
            "--state",
            str(tmp_path / "state.json"),
            "--questions",
            str(tmp_path / "questions.json"),
            "--retries",
            "0",
        ],
    )
    assert result.exit_code == 1 and not result.stdout
    with pytest.raises(ValueError):
        example.select(discovery(), {})


def test_bad_upstream_not_empty():
    for data in ({}, {"error": "upstream failure"}, {"records": None}):
        with pytest.raises(ValueError):
            example.candidates(data)


def test_gitomics_failure_propagates(monkeypatch):
    def failure(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(example.subprocess, "run", failure)
    with pytest.raises(subprocess.CalledProcessError):
        example.select(
            discovery(),
            {
                "answers": {
                    "dataset": {"type": "choice", "choice": "synthetic-barley-001", "confidence": 1}
                }
            },
            read=True,
        )
