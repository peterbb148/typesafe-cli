"""Keep Actions artifacts for the two newest successful CI/Release builds."""

import argparse
import json
import subprocess
from typing import Any

ARTIFACT_NAMES = {
    "binary-linux-x86_64",
    "binary-linux-arm64",
    "binary-macos-arm64",
    "binary-windows-x86_64",
    "python-distributions",
}
WORKFLOW_PATHS = {".github/workflows/ci.yml", ".github/workflows/release.yml"}


def github_api(endpoint: str, *, method: str = "GET", paginate: bool = False) -> Any:
    """Call GitHub through gh, failing immediately on API or authentication errors.

    Args:
        endpoint: Repository API endpoint.
        method: HTTP method to use.
        paginate: Whether to collect all response pages into one array.

    Returns:
        Decoded JSON response, or None for a successful deletion.
    """
    command = ["gh", "api", "--method", method, endpoint]
    if paginate:
        command.extend(["--paginate", "--slurp"])
    result = subprocess.run(command, check=True, stdout=subprocess.PIPE, text=True)
    return json.loads(result.stdout) if result.stdout else None


def select_artifacts(
    artifacts: list[dict[str, Any]], runs: dict[int, dict[str, Any]]
) -> tuple[set[int], list[dict[str, Any]]]:
    """Select completed build artifacts outside the two newest successful runs.

    Args:
        artifacts: Unexpired repository artifacts.
        runs: Run metadata indexed by run ID.

    Returns:
        Retained run IDs and artifacts eligible for deletion.
    """
    scoped = [
        artifact
        for artifact in artifacts
        if artifact["name"] in ARTIFACT_NAMES
        and not artifact["expired"]
        and runs[artifact["workflow_run"]["id"]]["path"] in WORKFLOW_PATHS
    ]
    run_ids = {artifact["workflow_run"]["id"] for artifact in scoped}
    successful = sorted(
        (
            run_id
            for run_id in run_ids
            if runs[run_id]["status"] == "completed" and runs[run_id]["conclusion"] == "success"
        ),
        key=lambda run_id: (runs[run_id]["created_at"], run_id),
        reverse=True,
    )
    retained = set(successful[:2])
    deletions = [
        artifact
        for artifact in scoped
        if artifact["workflow_run"]["id"] not in retained
        and runs[artifact["workflow_run"]["id"]]["status"] == "completed"
    ]
    return retained, deletions


def prune_artifacts(repository: str, *, apply: bool = False) -> None:
    """Preview or delete obsolete artifacts, rechecking runs before deletion.

    Args:
        repository: GitHub owner/repository name.
        apply: Whether to delete the selected artifacts.
    """
    base = f"repos/{repository}/actions"
    pages = github_api(f"{base}/artifacts?per_page=100", paginate=True)
    artifacts = [
        artifact
        for page in pages
        for artifact in page["artifacts"]
        if artifact["name"] in ARTIFACT_NAMES and not artifact["expired"]
    ]
    runs = {
        run_id: github_api(f"{base}/runs/{run_id}")
        for run_id in sorted({artifact["workflow_run"]["id"] for artifact in artifacts})
    }
    retained, deletions = select_artifacts(artifacts, runs)
    print(f"Retain successful build runs: {sorted(retained)}")
    print(
        f"Selected {len(deletions)} artifacts ({sum(a['size_in_bytes'] for a in deletions)} bytes)"
    )
    for run_id in sorted({artifact["workflow_run"]["id"] for artifact in deletions}):
        if apply:
            current = github_api(f"{base}/runs/{run_id}")
            if (
                current["status"] != "completed"
                or current["run_attempt"] != runs[run_id]["run_attempt"]
            ):
                print(f"Skip run {run_id}: active or rerun since selection")
                continue
        for artifact in deletions:
            if artifact["workflow_run"]["id"] != run_id:
                continue
            action = "Delete" if apply else "Would delete"
            print(f"{action} artifact {artifact['id']} from run {run_id}")
            if apply:
                github_api(f"{base}/artifacts/{artifact['id']}", method="DELETE")


def main() -> None:
    """Parse command-line arguments and run the retention operation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="GitHub owner/repository")
    parser.add_argument("--apply", action="store_true", help="Delete artifacts; default is preview")
    args = parser.parse_args()
    prune_artifacts(args.repo, apply=args.apply)


if __name__ == "__main__":
    main()
