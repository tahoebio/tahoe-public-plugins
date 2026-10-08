"""Shared test helpers.

``j`` joins fragments so a test file never contains, contiguously, a literal the
scanner looks for. ``git_repo`` and ``commit_all`` build throwaway repositories
for the history and packaging tests.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


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


def commit_message_without_trailing_newline(repo, message: str) -> str:
    """Commit the index with a message that has no trailing newline.

    ``git commit -m`` always appends one, so the boundary is built with
    ``git commit-tree`` (as GitHub squash commits can produce).
    """
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    tree = subprocess.run(
        ["git", "-C", str(repo), "write-tree"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    sha = subprocess.run(
        ["git", "-C", str(repo), "commit-tree", tree],
        input=message,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(["git", "-C", str(repo), "update-ref", "HEAD", sha], check=True)
    return sha


def shallow_clone(source, dest) -> Path:
    """Clone ``source`` with no history, as a shallow CI checkout would be."""
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{source}", str(dest)],
        check=True,
    )
    return Path(dest)
