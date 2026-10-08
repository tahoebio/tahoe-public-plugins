"""Shared test helpers.

``j`` joins fragments so a test file never contains, contiguously, a literal the
scanner looks for. ``git_repo`` and ``commit_all`` build throwaway repositories
for the history and packaging tests.
"""

from __future__ import annotations

import subprocess


def j(*parts: str) -> str:
    """Join fragments so a sensitive literal is never contiguous in source."""
    return "".join(parts)


def git_repo(path):
    """Initialise an empty git repository at ``path`` with a local identity."""
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "tester@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Tester"], check=True
    )
    return path


def commit_all(repo, message: str = "fixture") -> None:
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", message], check=True
    )
