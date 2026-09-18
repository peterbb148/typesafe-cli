"""Exercise an installed executable from a temporary home against a local mock server."""

import argparse
import json
import os
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Handler(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *args):
        pass

    def reply(self, status, value):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.headers.get("Authorization") != "Bearer smoke-fake-key":
            self.reply(401, {"error": "invalid mock key"})
            return
        self.reply(
            200,
            {
                "models": [
                    {"name": "jev-test", "description": "Mock", "release_date": "2026-01-01"}
                ],
                "extra": True,
            },
        )

    def do_POST(self):
        raw = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.requests.append(raw)
        answers = {}
        for name, question in raw["questions"].items():
            kind = question["type"]
            if kind == "noul":
                answers[name] = {"type": kind, "noul": 0.8}
            elif kind == "choice":
                labels = list(question["criteria"])
                answers[name] = {
                    "type": kind,
                    "choice": labels[0],
                    "probabilities": {k: float(i == 0) for i, k in enumerate(labels)},
                    "confidence": 1.0,
                }
            else:
                levels = question["criteria"]
                answers[name] = {
                    "type": kind,
                    "score": 0.0,
                    "legend": {str(i): v for i, v in enumerate(levels)},
                    "probabilities": {str(i): float(i == 0) for i in range(len(levels))},
                    "confidence": 1.0,
                }
        self.reply(
            200,
            {
                "model": "jev-test",
                "usage": {"input_tokens": 10, "output_tokens": 3},
                "answers": answers,
                "extra": True,
            },
        )


def run_smoke(executable, binary=False):
    executable = str(Path(executable).resolve())
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            env = {
                k: v
                for k, v in os.environ.items()
                if not k.startswith("TYPESAFE_") and k not in {"PYTHONPATH", "PYTHONHOME"}
            }
            env.update(
                HOME=directory,
                USERPROFILE=directory,
                TYPESAFE_BASE_URL=f"http://127.0.0.1:{server.server_port}",
                PYTHONIOENCODING="utf-8",
            )
            if binary:
                # The bundled executable cannot find Python/UV on PATH.
                env["PATH"] = str(home / "empty-path")

            def run(args, data=None, code=0, overrides=None):
                result = subprocess.run(
                    [executable, *args],
                    input=data,
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    cwd=home,
                    env=env | (overrides or {}),
                    timeout=60,
                )
                assert result.returncode == code, (
                    args,
                    result.returncode,
                    result.stdout,
                    result.stderr,
                )
                assert "smoke-fake-key" not in result.stdout + result.stderr
                if code:
                    assert not result.stdout and result.stderr
                    return result
                return result

            run(["--help"])
            version = run(["--version"]).stdout.strip()
            assert version
            run(["models", "list", "--help"])
            run(["auth", "login", "--api-key-stdin"], "smoke-fake-key\n")
            path = home / ".config/typesafe-cli/credentials.json"
            assert path.exists()
            if os.name != "nt":
                assert path.stat().st_mode & 0o777 == 0o600
                assert path.parent.stat().st_mode & 0o777 == 0o700
            else:
                import win32api
                import win32con
                import win32security

                token = win32security.OpenProcessToken(
                    win32api.GetCurrentProcess(), win32con.TOKEN_QUERY
                )
                try:
                    user = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
                finally:
                    token.Close()
                for item in (path, path.parent):
                    descriptor = win32security.GetNamedSecurityInfo(
                        str(item),
                        win32security.SE_FILE_OBJECT,
                        win32security.DACL_SECURITY_INFORMATION,
                    )
                    acl = descriptor.GetSecurityDescriptorDacl()
                    assert acl is not None and acl.GetAceCount() > 0
                    for index in range(acl.GetAceCount()):
                        ace = acl.GetAce(index)
                        assert ace[0][0] == win32security.ACCESS_ALLOWED_ACE_TYPE, ace
                        assert ace[2] == user, ace

                    assert (
                        descriptor.GetSecurityDescriptorControl()[0]
                        & win32security.SE_DACL_PROTECTED
                    )
            assert json.loads(run(["auth", "status"]).stdout)["source"] == "file"
            models = json.loads(run(["models", "list"]).stdout)
            assert models["extra"]
            run(
                ["models", "list", "--retries", "0"],
                code=1,
                overrides={"TYPESAFE_API_KEY": "bad-override"},
            )
            assert json.loads(path.read_text())["api_key"] == "smoke-fake-key"
            for name in ("noul", "choice", "score", "questions"):
                questions = str(ROOT / "examples" / f"{name}.json")
                args = ["evaluate", "--questions", questions, "--model", "jev-test"]
                output = json.loads(run(args + ["--state", "-"], '{"document":"α"}').stdout)
                assert output["model"] == "jev-test" and output["extra"]
                run(args + ["--state", str(ROOT / "examples/state.json")])
                run(args + ["--state", "-", "--state-format", "text"], "raw α text")
                run(args + ["--state", "-"], "{broken", code=2)
            run(["auth", "logout"])
            assert not path.exists()
            run(["models", "list"], code=1)
            assert not json.loads(run(["auth", "status"]).stdout)["configured"]
            print(f"Artifact smoke passed: {version} (binary={binary}, mock provider only)")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("executable")
    parser.add_argument("--binary", action="store_true")
    args = parser.parse_args()
    run_smoke(args.executable, args.binary)
