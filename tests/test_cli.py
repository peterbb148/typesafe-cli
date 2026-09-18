import json
import os
from pathlib import Path

import httpx2
import pytest
from typer.testing import CliRunner
from typesafe_sdk import TypeSafeClient

from typesafe_cli import __version__, adapter, auth
from typesafe_cli.cli import app
from typesafe_cli.errors import ConfigError

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[1]


def invoke(args, **kwargs):
    return runner.invoke(app, args, **kwargs)


@pytest.mark.parametrize(
    "args", [["--help"], ["--version"], ["models", "--help"], ["evaluate", "--help"]]
)
def test_help(args):
    result = invoke(args)
    assert result.exit_code == 0, result.output
    assert not auth.credential_path().exists()
    if args == ["--version"]:
        assert result.stdout.strip() == __version__


def test_auth_lifecycle(monkeypatch):
    key = "fake-test-secret"
    result = invoke(["auth", "login", "--api-key-stdin"], input=key + "\n")
    assert result.exit_code == 0, result.output
    assert key not in result.output
    assert json.loads(result.stdout)["saved"]
    assert auth.resolve() == (key, "file")
    if os.name != "nt":
        assert auth.credential_path().stat().st_mode & 0o777 == 0o600
        assert auth.credential_path().parent.stat().st_mode & 0o777 == 0o700
    result = invoke(["auth", "status"])
    assert json.loads(result.stdout) == {
        "configured": True,
        "source": "file",
        "provider_validated": False,
    }
    before = auth.credential_path().read_bytes()
    monkeypatch.setenv("TYPESAFE_API_KEY", "override-secret")
    assert auth.resolve() == ("override-secret", "environment")
    assert auth.credential_path().read_bytes() == before
    unrelated = auth.credential_path().parent / "settings.json"
    unrelated.write_text("{}")
    result = invoke(["auth", "logout"])
    assert json.loads(result.stdout)["environment_override_active"]
    assert not auth.credential_path().exists()
    assert unrelated.exists()
    assert invoke(["auth", "logout"]).exit_code == 0


def test_empty_login_preserves_key():
    auth.save("previous")
    result = invoke(["auth", "login", "--api-key-stdin"], input=" ")
    assert result.exit_code == 2
    assert result.stdout == ""
    assert auth.resolve()[0] == "previous"


def test_hidden_login(monkeypatch):
    import sys

    import typer

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    seen = {}

    def prompt(*args, **kwargs):
        seen.update(kwargs)
        return "hidden-secret"

    monkeypatch.setattr(typer, "prompt", prompt)
    # CliRunner replaces stdin, so invoke the command function directly.
    from typesafe_cli.cli import login

    login(False)
    assert seen["hide_input"] and seen["err"]
    assert auth.resolve()[0] == "hidden-secret"


def test_failed_write_preserves_key(monkeypatch):
    auth.save("previous")

    def fail(*args):
        raise OSError("secret should not escape")

    monkeypatch.setattr(os, "replace", fail)
    result = invoke(["auth", "login", "--api-key-stdin"], input="new-secret")
    assert result.exit_code == 1
    assert "new-secret" not in result.output
    assert auth.resolve()[0] == "previous"
    assert not list(auth.credential_path().parent.glob(".credentials-*"))


def test_malformed_credentials():
    auth.save("previous")
    auth.credential_path().write_text("not-json-secret")
    result = invoke(["auth", "status"])
    assert result.exit_code == 1 and not result.stdout
    assert "not-json-secret" not in result.output


@pytest.mark.skipif(os.name == "nt", reason="POSIX modes")
def test_insecure_credentials_rejected():
    auth.save("previous")
    auth.credential_path().chmod(0o644)
    with pytest.raises(ConfigError):
        auth.resolve()


def install_transport(monkeypatch, handler):
    captured = {}

    def client(**kwargs):
        captured.update(kwargs)
        obj = TypeSafeClient(**kwargs, transport=httpx2.MockTransport(handler))
        captured["client"] = obj
        return obj

    monkeypatch.setattr(adapter.sdk, "TypeSafeClient", client)
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake")
    return captured


def test_models_preserves_metadata(monkeypatch):
    body = {
        "models": [
            {"name": "jev-test", "description": "Test", "release_date": "2026-01-01", "extra": True}
        ],
        "future": 1,
    }
    captured = install_transport(monkeypatch, lambda r: httpx2.Response(200, json=body))
    result = invoke(["models", "list", "--timeout", "12", "--retries", "0"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == body
    assert not result.stderr
    assert captured["timeout"] == 12
    assert captured["retry"].max_retries == 0
    assert captured["retry"].timeout == 60
    assert captured["client"]._http_client.is_closed


@pytest.mark.parametrize(
    "code,diagnostic",
    [
        (401, "Authentication"),
        (403, "Access denied"),
        (429, "Rate limit"),
        (500, "rejected"),
        (422, "rejected"),
    ],
)
def test_provider_errors(monkeypatch, code, diagnostic):
    install_transport(
        monkeypatch, lambda r: httpx2.Response(code, json={"message": "private-state-secret"})
    )
    result = invoke(["models", "list", "--retries", "0"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert diagnostic in result.stderr
    assert "private-state-secret" not in result.output


@pytest.mark.parametrize("error", [httpx2.ConnectError, httpx2.ReadTimeout])
def test_network_errors(monkeypatch, error):
    def handler(request):
        raise error("private-secret", request=request)

    install_transport(monkeypatch, handler)
    result = invoke(["models", "list", "--retries", "0"])
    assert result.exit_code == 1 and not result.stdout
    assert "private-secret" not in result.stderr


def test_missing_key():
    result = invoke(["models", "list"])
    assert result.exit_code == 1 and not result.stdout
    assert "auth login" in result.stderr


@pytest.mark.parametrize("state", [{"x": [1, True, None]}, ["α", 1], "hello"])
def test_mixed_evaluation(monkeypatch, state):
    seen = []
    response = {
        "model": "jev-1.13.0",
        "usage": {"input_tokens": 1, "output_tokens": 2, "future": 3},
        "answers": {
            "billing": {"type": "noul", "noul": 0.9},
            "tone": {
                "type": "choice",
                "choice": "frustrated",
                "probabilities": {"calm": 0.1, "frustrated": 0.9},
                "confidence": 0.8,
            },
            "urgency": {
                "type": "score",
                "score": 1.5,
                "legend": {"0": "can wait", "1": "this week", "2": "today"},
                "probabilities": {"0": 0.1, "1": 0.3, "2": 0.6},
                "confidence": 0.6,
            },
        },
        "extra": "preserved",
    }

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx2.Response(200, json=response)

    install_transport(monkeypatch, handler)
    result = invoke(
        [
            "evaluate",
            "--state",
            "-",
            "--questions",
            str(ROOT / "examples/questions.json"),
            "--model",
            "jev-1.13.0",
        ],
        input=json.dumps(state),
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == response
    assert len(seen) == 1 and seen[0]["state"] == state
    assert seen[0]["questions"]["tone"]["instructions"] == {"question": "What is the tone?"}
    assert seen[0]["questions"]["tone"]["criteria"]["frustrated"] == {
        "description": "Expresses frustration"
    }


@pytest.mark.parametrize("state", ["{broken", "42", "null", "true", '{"x":NaN}', '{"x":1,"x":2}'])
def test_invalid_state(state):
    result = invoke(
        ["evaluate", "--state", "-", "--questions", str(ROOT / "examples/questions.json")],
        input=state,
    )
    assert result.exit_code == 2 and not result.stdout


@pytest.mark.parametrize(
    "questions",
    [
        {},
        [],
        {"x": {"type": "unknown"}},
        {"x": {"type": "choice", "criteria": {}}},
        {"x": {"type": "score", "criteria": []}},
        {"x": {"type": "noul", "typo": True}},
    ],
)
def test_invalid_questions(tmp_path, questions):
    path = tmp_path / "q.json"
    path.write_text(json.dumps(questions))
    result = invoke(["evaluate", "--state", "-", "--questions", str(path)], input="{}")
    assert result.exit_code == 2 and not result.stdout


def test_text_files_and_unreadable(monkeypatch, tmp_path):
    path = tmp_path / "state.txt"
    path.write_text("raw α text", encoding="utf-8")
    seen = []

    def call(op, **kwargs):
        seen.append(kwargs["state"])
        return {"answers": {}}

    monkeypatch.setattr(adapter, "call", call)
    args = ["evaluate", "--state", str(path), "--questions", str(ROOT / "examples/noul.json")]
    assert invoke(args + ["--state-format", "text"]).exit_code == 0
    assert seen == ["raw α text"]
    path.unlink()
    result = invoke(args)
    assert result.exit_code == 2 and not result.stdout


def test_invalid_response(monkeypatch):
    install_transport(monkeypatch, lambda r: httpx2.Response(200, json={"models": "bad"}))
    result = invoke(["models", "list"])
    assert result.exit_code == 1 and not result.stdout


def test_retry_attempts_are_owned_by_sdk(monkeypatch):
    attempts = []

    def handler(request):
        attempts.append(request)
        return httpx2.Response(429, json={"error": "rate limited"}, headers={"Retry-After": "0"})

    install_transport(monkeypatch, handler)
    result = invoke(["models", "list", "--retries", "2"])
    assert result.exit_code == 1 and not result.stdout
    assert len(attempts) == 3


def test_overflow_rejected_before_request():
    result = invoke(
        ["evaluate", "--state", "-", "--questions", str(ROOT / "examples/questions.json")],
        input='{"x":1e999}',
    )
    assert result.exit_code == 2 and not result.stdout


def test_no_provider_content_logs(monkeypatch, caplog):
    import logging

    install_transport(
        monkeypatch, lambda r: httpx2.Response(401, json={"message": "private-secret"})
    )
    monkeypatch.setenv("TYPESAFE_LOG_LEVEL", "debug")
    with caplog.at_level(logging.DEBUG):
        result = invoke(["models", "list", "--retries", "0"])
    assert result.exit_code == 1
    assert "private-secret" not in caplog.text


def test_corrupt_file_ignored_by_environment(monkeypatch):
    auth.save("old-key")
    auth.credential_path().write_text("broken")
    monkeypatch.setenv("TYPESAFE_API_KEY", "new-key")
    assert auth.resolve() == ("new-key", "environment")
