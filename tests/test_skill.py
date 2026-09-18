import json
import re
from pathlib import Path

import httpx2
import yaml
from typer.testing import CliRunner
from typesafe_sdk import TypeSafeClient

from typesafe_cli import adapter
from typesafe_cli.cli import app

ROOT = Path(__file__).resolve().parents[1]


def test_portable_skill_examples(tmp_path, monkeypatch):
    import shutil

    folder = tmp_path / "typesafe-cli"
    shutil.copytree(ROOT / "skills/typesafe-cli", folder)
    text = (folder / "SKILL.md").read_text(encoding="utf-8")
    metadata = yaml.safe_load(text.split("---", 2)[1])
    assert metadata["name"] == "typesafe-cli" and metadata["description"]
    for document in folder.rglob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            if not link.startswith("https://"):
                assert (document.parent / link).exists()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake")

    def handler(request):
        body = json.loads(request.content)
        assert isinstance(body["state"], dict)
        answers = {}
        for key, q in body["questions"].items():
            if q["type"] == "noul":
                answers[key] = {"type": "noul", "noul": 0.5}
            elif q["type"] == "choice":
                first = next(iter(q["criteria"]))
                answers[key] = {
                    "type": "choice",
                    "choice": first,
                    "probabilities": {first: 1.0},
                    "confidence": 1.0,
                }
            else:
                answers[key] = {
                    "type": "score",
                    "score": 0.0,
                    "legend": {"0": q["criteria"][0]},
                    "probabilities": {"0": 1.0},
                    "confidence": 1.0,
                }
        return httpx2.Response(
            200,
            json={
                "model": "jev-test",
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "answers": answers,
            },
        )

    monkeypatch.setattr(
        adapter.sdk,
        "TypeSafeClient",
        lambda **kw: TypeSafeClient(**kw, transport=httpx2.MockTransport(handler)),
    )
    for name in ("choice", "score", "noul", "questions"):
        result = CliRunner().invoke(
            app,
            [
                "evaluate",
                "--state",
                str(folder / "references/state.json"),
                "--questions",
                str(folder / f"references/{name}.json"),
            ],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["answers"]
