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


def _rev_parse(repo, ref: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", ref],
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


def test_an_empty_commit_with_a_forbidden_message_is_scanned(tmp_path):
    # An empty commit changes no path. A path-limited `git log` omits it, so a
    # forbidden token in its MESSAGE would evade the gate entirely.
    repo = git_repo(tmp_path)
    _commit(repo, "note.md", "clean\n", "clean base")
    _git(
        repo,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "note " + j("s3", "://bucket"),
    )

    assert common.scan_history(repo)
    with pytest.raises(common.ResidueError):
        validate.validate_residue(repo)


def test_a_merge_commit_message_is_scanned(tmp_path):
    repo = git_repo(tmp_path)
    base = _base_branch(repo)
    _commit(repo, "note.md", "base\n", "base")
    _git(repo, "checkout", "-q", "-b", "side")
    _commit(repo, "side.md", "side\n", "side")
    _git(repo, "checkout", "-q", base)
    _commit(repo, "other.md", "other\n", "other")
    _git(repo, "merge", "-q", "--no-ff", "side", "-m", "merge " + j("s3", "://bucket"))

    assert common.scan_history(repo)


def test_an_annotated_tag_message_is_scanned(tmp_path):
    # The target commit is clean; the offence is only in the tag OBJECT, which
    # `git log` (a commit walk) never reads. A TAG-push run scans the tag ref.
    repo = git_repo(tmp_path)
    _commit(repo, "note.md", "clean\n", "clean base")
    _git(repo, "tag", "-a", "v1", "-m", "release " + j("s3", "://bucket"))

    assert j("s3", "://") not in (repo / "note.md").read_text()
    # A branch scan of HEAD does not read a tag object...
    assert common.scan_history(repo) == []
    # ...but scanning the tag ref does.
    assert common.scan_history(repo, ref="refs/tags/v1")
    with pytest.raises(common.ResidueError):
        validate.validate_residue(repo, ref="refs/tags/v1")


def test_a_lightweight_tag_has_no_tag_object_to_scan(tmp_path):
    repo = git_repo(tmp_path)
    _commit(repo, "note.md", "clean\n", "clean base")
    _git(repo, "tag", "v1")

    # A lightweight tag is just a ref to a commit; its scan is the commit's.
    assert common.scan_history(repo, ref="refs/tags/v1") == []


def test_an_unrelated_dirty_tag_does_not_fail_a_clean_branch(tmp_path):
    # Per-ref isolation: a tag on an older commit is another ref's problem, so a
    # clean branch must not fail because someone tagged its ancestor.
    repo = git_repo(tmp_path)
    base = _base_branch(repo)
    _commit(repo, "note.md", "clean\n", "clean base")
    older = _rev_parse(repo, "HEAD")
    _commit(repo, "note.md", "clean v2\n", "clean v2")
    _git(repo, "tag", "-a", "old", "-m", "x " + j("s3", "://bucket"), older)

    assert common.scan_history(repo) == []
    validate.validate_residue(repo)
    # The dirty tag is still dirty on its own ref.
    assert common.scan_history(repo, ref="refs/tags/old")


def test_a_clean_tag_next_to_a_dirty_sibling_passes(tmp_path):
    repo = git_repo(tmp_path)
    _commit(repo, "note.md", "clean\n", "clean base")
    _git(repo, "tag", "-a", "clean", "-m", "a clean release note")
    _git(repo, "tag", "-a", "dirty", "-m", "x " + j("s3", "://bucket"))

    validate.validate_residue(repo, ref="refs/tags/clean")
    assert common.scan_history(repo, ref="refs/tags/clean") == []
    with pytest.raises(common.ResidueError):
        validate.validate_residue(repo, ref="refs/tags/dirty")


def test_sweep_scans_annotated_tags(tmp_path, capsys):
    from scripts import sweep_branches

    repo = git_repo(tmp_path)
    _commit(repo, "note.md", "clean\n", "clean base")
    base = _base_branch(repo)
    _git(repo, "update-ref", "refs/remotes/origin/base", f"refs/heads/{base}")
    _git(repo, "tag", "-a", "v1", "-m", "release " + j("s3", "://bucket"))

    reports = sweep_branches.branch_reports(repo)
    tags = [report for report in reports if report["kind"] == "tag"]
    assert tags and tags[0]["ok"] is False
    assert tags[0]["author"], "a tag finding must name its tagger"

    assert sweep_branches.main(["--root", str(repo)]) == 0
    assert "tag/v1" in capsys.readouterr().out


def test_sweep_reports_a_dirty_lightweight_tag(tmp_path, capsys):
    # A lightweight tag can be the SOLE ref to a dirty commit; the sweep must
    # enumerate every tag, not only annotated ones.
    from scripts import sweep_branches

    repo = git_repo(tmp_path)
    base = _base_branch(repo)
    _commit(repo, "note.md", "clean\n", "clean base")
    _git(repo, "checkout", "-q", "-b", "side")
    _commit(repo, "note.md", _offending(), "dirty on side")
    dirty = _rev_parse(repo, "HEAD")
    _git(repo, "checkout", "-q", base)
    _git(repo, "branch", "-q", "-D", "side")
    _git(repo, "tag", "light-orphan", dirty)
    _git(repo, "update-ref", "refs/remotes/origin/base", f"refs/heads/{base}")

    reports = sweep_branches.branch_reports(repo)
    orphan = next(r for r in reports if r["branch"] == "tag/light-orphan")
    assert orphan["ok"] is False

    assert sweep_branches.main(["--root", str(repo)]) == 0
    assert "tag/light-orphan" in capsys.readouterr().out



def test_ci_scans_tag_pushes_too():
    text = (common.REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "tags:" in text, "a tag push must still run the leak scan"


def test_ci_scans_the_pushed_tag_object():
    text = (common.REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    # On a tag push HEAD is the tag's TARGET commit, so CI must name the tag ref.
    assert "refs/tags/" in text


def test_sweep_workflow_keeps_a_credential_to_fetch_every_branch():
    text = (common.REPO_ROOT / ".github/workflows/sweep.yml").read_text(encoding="utf-8")
    # The origin is private until publication: the sweep's fetch needs a token.
    assert "persist-credentials: false" not in text
    assert "fetch" in text


def test_sweep_workflow_fetches_tag_objects():
    text = (common.REPO_ROOT / ".github/workflows/sweep.yml").read_text(encoding="utf-8")
    # Annotated tag messages are scanned, so the sweep needs the tag objects.
    assert "refs/tags" in text


def test_ci_fetches_tag_objects():
    text = (common.REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "fetch-tags: true" in text
