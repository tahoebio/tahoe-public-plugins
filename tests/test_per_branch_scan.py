"""The per-branch leak scan.

CI must judge a commit on its own history: a leaked literal on someone else's
branch must not fail a clean branch, and a leaked literal in the branch's own
history must fail it. The whole-history sweep is a separate, reporting-only job.
"""

import subprocess

import pytest

from helpers import commit_all, git_repo, j
from scripts import common, validate


def _offending(text: str = "note") -> str:
    return f"{text}: " + j("s3", "://bucket") + "\n"


def _git(repo, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _base_branch(repo) -> str:
    """The initial branch name of a fresh repository (git's default varies)."""
    return subprocess.run(
        ["git", "-C", str(repo), "symbolic-ref", "--short", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo, rel: str, content: str, message: str) -> None:
    (repo / rel).write_text(content)
    commit_all(repo, message)


def _dirty_sibling(repo) -> str:
    """Commit an offending line on a sibling branch, then return to the base."""
    base = _base_branch(repo)
    _git(repo, "checkout", "-q", "-b", "dirty")
    _commit(repo, "note.md", _offending(), "dirty commit")
    _git(repo, "checkout", "-q", base)
    return base


def test_a_clean_head_passes_while_an_unrelated_branch_is_dirty(tmp_path):
    repo = git_repo(tmp_path)
    _commit(repo, "note.md", "clean\n", "clean base")
    _dirty_sibling(repo)

    # HEAD (the clean branch) validates: an unrelated branch cannot fail it.
    validate.validate_residue(repo)
    assert common.scan_history(repo) == []

    # The dirty branch is still dirty when scanned by its own ref.
    assert common.scan_history(repo, ref="refs/heads/dirty")


def test_the_same_offending_commit_reachable_from_head_fails(tmp_path):
    repo = git_repo(tmp_path)
    _commit(repo, "note.md", _offending(), "offending commit")
    with pytest.raises(common.ResidueError):
        validate.validate_residue(repo)


def test_all_refs_flag_restores_the_whole_history_scan(tmp_path):
    repo = git_repo(tmp_path)
    _commit(repo, "note.md", "clean\n", "clean base")
    _dirty_sibling(repo)

    # Default: HEAD only. The --all-refs escape hatch restores the old sweep.
    assert common.scan_history(repo, all_refs=False) == []
    assert common.scan_history(repo, all_refs=True)


def test_validate_residue_all_refs_scans_every_branch(tmp_path):
    repo = git_repo(tmp_path)
    _commit(repo, "note.md", "clean\n", "clean base")
    _dirty_sibling(repo)

    validate.validate_residue(repo)
    with pytest.raises(common.ResidueError):
        validate.validate_residue(repo, all_refs=True)


def test_sweep_reports_the_dirty_branch_and_author_and_exits_zero(tmp_path, capsys):
    from scripts import sweep_branches

    repo = git_repo(tmp_path)
    _commit(repo, "note.md", "clean\n", "clean base")
    base = _dirty_sibling(repo)
    # Publish both branches as remote-tracking refs, as CI would see them.
    _git(repo, "update-ref", "refs/remotes/origin/base", f"refs/heads/{base}")
    _git(repo, "update-ref", "refs/remotes/origin/dirty", "refs/heads/dirty")

    reports = sweep_branches.branch_reports(repo)
    by_name = {report["branch"]: report for report in reports}
    assert by_name["origin/base"]["ok"] is True
    dirty = by_name["origin/dirty"]
    assert dirty["ok"] is False
    assert dirty["findings"] >= 1
    assert dirty["commit"] and dirty["author"] and "Tester" in dirty["author"]

    # The sweep reports; it never fails unrelated work.
    assert sweep_branches.main(["--root", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "origin/dirty" in out
    assert "Tester" in out


def test_sweep_does_not_fail_on_a_clean_repository(tmp_path, capsys):
    from scripts import sweep_branches

    repo = git_repo(tmp_path)
    _commit(repo, "note.md", "clean\n", "clean base")
    base = _base_branch(repo)
    _git(repo, "update-ref", "refs/remotes/origin/base", f"refs/heads/{base}")

    assert sweep_branches.main(["--root", str(repo)]) == 0
    assert "origin/base" in capsys.readouterr().out


def test_sweep_fails_loudly_when_it_finds_no_branches(tmp_path, capsys):
    from scripts import sweep_branches

    repo = git_repo(tmp_path)
    _commit(repo, "note.md", "clean\n", "clean base")

    # No remote-tracking refs: reporting "0/0 branches clean" would be a silent
    # pass, so the sweep must fail instead.
    assert sweep_branches.main(["--root", str(repo)]) == 1
    assert "no remote branches" in capsys.readouterr().err


def test_a_merged_parent_commit_is_still_scanned(tmp_path):
    # A side commit that the merge resolution reverts (an "ours" merge) is still
    # in HEAD's ancestry. Path-history simplification would drop it; the scan
    # must not.
    repo = git_repo(tmp_path)
    base = _base_branch(repo)
    _commit(repo, "note.md", "base\n", "base")
    _git(repo, "checkout", "-q", "-b", "side")
    _commit(repo, "note.md", _offending(), "side adds the offence")
    _git(repo, "checkout", "-q", base)
    _commit(repo, "note.md", "base v2\n", "base v2")
    _git(repo, "merge", "-q", "-s", "ours", "side", "-m", "merge side (ours)")

    # The offence is not in the working tree, but it is in HEAD's ancestry.
    assert j("s3", "://") not in (repo / "note.md").read_text()
    assert common.scan_history(repo)
    with pytest.raises(common.ResidueError):
        validate.validate_residue(repo)


def test_binary_findings_carry_the_offending_commit(tmp_path):
    repo = git_repo(tmp_path)
    (repo / "blob.bin").write_bytes(b"\xff\xfe\x00\x01\x02")
    commit_all(repo, "add a binary")

    findings = common.scan_history(repo)
    assert findings and findings[0]["label"] == "unscannable-file"
    assert findings[0]["commit"], "a binary finding must name its commit"


def test_ci_scans_tag_pushes_too():
    text = (common.REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "tags:" in text, "a tag push must still run the leak scan"


def test_sweep_workflow_keeps_a_credential_to_fetch_every_branch():
    text = (common.REPO_ROOT / ".github/workflows/sweep.yml").read_text(encoding="utf-8")
    # The origin is private until publication: the sweep's fetch needs a token.
    assert "persist-credentials: false" not in text
    assert "fetch" in text
