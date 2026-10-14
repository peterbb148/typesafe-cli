"""Verify retention boundaries and GitHub API orchestration without deleting live artifacts."""

import importlib.util
import subprocess
from pathlib import Path
from typing import Any

import pytest

SPEC = importlib.util.spec_from_file_location(
    "prune_artifacts", Path(__file__).resolve().parents[1] / "scripts/prune_artifacts.py"
)
retention = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retention)


def run(
    run_id: int,
    *,
    status: str = "completed",
    conclusion: str | None = "success",
    path: str = ".github/workflows/ci.yml",
) -> dict[str, Any]:
    """Create API run metadata with an ordered creation timestamp."""
    return {
        "id": run_id,
        "created_at": f"2026-10-14T00:{run_id:02}:00Z",
        "status": status,
        "conclusion": conclusion,
        "path": path,
        "run_attempt": 1,
    }


def artifact(run_id: int, name: str = "binary-linux-x86_64") -> dict[str, Any]:
    """Create an unexpired Actions artifact for a run."""
    return {
        "id": run_id * 10 + sorted(retention.ARTIFACT_NAMES).index(name),
        "name": name,
        "workflow_run": {"id": run_id},
        "expired": False,
        "size_in_bytes": 100,
    }


def test_keep_two_build_sets_across_ci_and_release() -> None:
    """Keep every platform together, combining workflows and ignoring input ordering."""
    runs = {
        3: run(3),
        1: run(1),
        2: run(2, path=".github/workflows/release.yml"),
    }
    artifacts = [artifact(i, name) for i in runs for name in retention.ARTIFACT_NAMES]
    kept, deleted = retention.select_artifacts(artifacts, runs)
    assert kept == {2, 3}
    assert {a["id"] for a in deleted} == {
        artifact(1, name)["id"] for name in retention.ARTIFACT_NAMES
    }


def test_protect_active_runs_and_ignore_unrelated_artifacts() -> None:
    """Failed runs cannot displace successes; active and unrelated data survives."""
    runs = {
        1: run(1),
        2: run(2),
        3: run(3, conclusion="failure"),
        4: run(4, status="in_progress", conclusion=None, path=".github/workflows/release.yml"),
        5: run(5, status="queued", conclusion=None),
        6: run(6, path=".github/workflows/unrelated.yml"),
        7: run(7, conclusion="cancelled"),
        8: run(8),
    }
    artifacts = [artifact(i) for i in runs]
    artifacts[-1]["expired"] = True
    unrelated = {**artifact(3), "id": 999, "name": "test-results"}
    kept, deleted = retention.select_artifacts([*artifacts, unrelated], runs)
    assert kept == {1, 2}
    assert {a["workflow_run"]["id"] for a in deleted} == {3, 7}


@pytest.mark.parametrize("count", [0, 1, 2])
def test_fewer_than_three_successes_are_preserved(count: int) -> None:
    """Do not remove existing successful builds before a third is available."""
    runs = {i: run(i) for i in range(1, count + 1)}
    kept, deleted = retention.select_artifacts([artifact(i) for i in runs], runs)
    assert kept == set(runs)
    assert deleted == []


@pytest.mark.parametrize("apply", [False, True])
def test_api_pagination_preview_and_deletion(monkeypatch: pytest.MonkeyPatch, apply: bool) -> None:
    """Inspect all pages and delete only obsolete artifact IDs when apply is explicit."""
    calls = []
    base = "repos/owner/repo/actions"

    def api(endpoint: str, **kwargs: Any) -> Any:
        """Serve API responses and record requests."""
        calls.append((endpoint, kwargs))
        if endpoint == f"{base}/artifacts?per_page=100":
            assert kwargs == {"paginate": True}
            return [{"artifacts": [artifact(3), artifact(2)]}, {"artifacts": [artifact(1)]}]
        if "/runs/" in endpoint:
            return run(int(endpoint.rsplit("/", 1)[1]))
        assert endpoint == f"{base}/artifacts/{artifact(1)['id']}"
        assert kwargs == {"method": "DELETE"}

    monkeypatch.setattr(retention, "github_api", api)
    retention.prune_artifacts("owner/repo", apply=apply)
    deletes = [endpoint for endpoint, kwargs in calls if kwargs.get("method") == "DELETE"]
    assert len(deletes) == int(apply)
    assert sum(endpoint == f"{base}/runs/1" for endpoint, _ in calls) == 1 + int(apply)


@pytest.mark.parametrize("change", [{"status": "in_progress"}, {"run_attempt": 2}])
def test_rerun_is_protected_before_deletion(
    monkeypatch: pytest.MonkeyPatch, change: dict[str, Any]
) -> None:
    """Skip a build that was restarted after the inventory snapshot."""
    reads = 0

    def api(endpoint: str, **kwargs: Any) -> Any:
        """Simulate a rerun between selection and deletion."""
        nonlocal reads
        assert kwargs.get("method") != "DELETE"
        if "/artifacts?" in endpoint:
            return [{"artifacts": [artifact(i) for i in (1, 2, 3)]}]
        run_id = int(endpoint.rsplit("/", 1)[1])
        if run_id == 1:
            reads += 1
            if reads == 2:
                return {**run(1), **change}
        return run(run_id)

    monkeypatch.setattr(retention, "github_api", api)
    retention.prune_artifacts("owner/repo", apply=True)
    assert reads == 2


def test_api_failure_stops_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """An API error must propagate instead of reporting a successful cleanup."""

    def fail(*args: Any, **kwargs: Any) -> None:
        """Simulate an authentication or transport failure."""
        raise subprocess.CalledProcessError(1, ["gh", "api"])

    monkeypatch.setattr(retention.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        retention.prune_artifacts("owner/repo", apply=True)
