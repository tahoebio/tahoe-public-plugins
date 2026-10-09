"""Packaging: the exact manifest files only, with loud refusal of unsafe paths."""

import shutil

import pytest

from helpers import commit_all, git_repo, j
from scripts import common, package

MANIFESTS = {
    "plugins/tara/plugin.json": '{"name": "tara", "version": "1.0.0"}\n',
    "plugins/tara/mcp.json": '{"mcpServers": {}}\n',
    "plugins/tara/.claude-plugin/plugin.json": '{"name": "tara"}\n',
    "plugins/tara/skills/tara/SKILL.md": "---\nname: tara\n---\n\n# tara\n",
    "plugins/tara/skills/tara/references/analysis-guidelines.md": "# Guidelines\n",
    "plugins/tara/skills/tara/references/data-catalog.md": "# Catalog\n",
    "plugins/tara/skills/tara/references/tool-routing.md": "# Routing\n",
}


def _write(root, rel, content="x\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _write_manifests(root):
    for rel, content in MANIFESTS.items():
        _write(root, rel, content)


def test_collect_keeps_exactly_the_allowlisted_manifests(tmp_path):
    _write_manifests(tmp_path)
    _write(tmp_path, "plugins/tara/assets/README.md", "assets\n")
    rels = list(MANIFESTS) + ["plugins/tara/assets/README.md", "README.md"]

    members = common.collect_archive_members(tmp_path, rels)
    assert members == sorted(common.ARCHIVE_ALLOWLIST)
    assert "plugins/tara/.claude-plugin/plugin.json" in members
    assert "plugins/tara/assets/README.md" not in members


def test_unlisted_and_hidden_files_are_excluded_not_refused(tmp_path):
    _write_manifests(tmp_path)
    _write(tmp_path, "plugins/tara/.hidden", "x\n")
    _write(tmp_path, "plugins/tara/bundle.zip", "x\n")
    rels = list(MANIFESTS) + ["plugins/tara/.hidden", "plugins/tara/bundle.zip"]

    members = common.collect_archive_members(tmp_path, rels)
    assert members == sorted(common.ARCHIVE_ALLOWLIST)


def test_missing_allowlisted_manifest_is_an_error(tmp_path):
    _write(tmp_path, "plugins/tara/plugin.json", "{}\n")
    with pytest.raises(common.PackagingError):
        common.collect_archive_members(tmp_path, ["plugins/tara/plugin.json"])


def test_reject_escaping_symlink(tmp_path):
    _write_manifests(tmp_path)
    link = tmp_path / "plugins" / "tara" / "plugin.json"
    link.unlink()
    link.symlink_to(tmp_path / "outside.json")

    with pytest.raises(common.PackagingError):
        common.collect_archive_members(tmp_path, list(MANIFESTS))


def test_archive_is_deterministic(tmp_path):
    _write_manifests(tmp_path)
    members = common.collect_archive_members(tmp_path, list(MANIFESTS))

    first = common.build_archive(tmp_path, members, tmp_path / "a.zip")
    second = common.build_archive(tmp_path, members, tmp_path / "b.zip")
    assert common.sha256_file(first) == common.sha256_file(second)
    assert first.read_bytes() == second.read_bytes()


def test_checksum_matches_archive(tmp_path):
    _write_manifests(tmp_path)
    members = common.collect_archive_members(tmp_path, list(MANIFESTS))
    archive = common.build_archive(tmp_path, members, tmp_path / "tara.zip")

    checksum = common.write_checksum(archive)
    assert checksum.read_text().split()[0] == common.sha256_file(archive)


def test_repo_archive_is_exactly_the_manifest_files():
    members = common.collect_archive_members(common.REPO_ROOT, common.tracked_files())
    assert members == sorted(common.ARCHIVE_ALLOWLIST)


def test_repo_archive_has_no_residue(tmp_path):
    archive, _ = package.build_release(common.REPO_ROOT, tmp_path)
    assert common.scan_archive(archive) == []


def test_build_release_refuses_an_archive_with_residue(tmp_path):
    repo = git_repo(tmp_path)
    for rel, content in MANIFESTS.items():
        _write(repo, rel, content)
    _write(
        repo, "plugins/tara/mcp.json", '{"note": "' + j("s3", "://bucket") + '"}\n'
    )
    commit_all(repo)

    out = repo / "dist"
    with pytest.raises(common.ResidueError):
        package.build_release(repo, out)
    assert not (out / "tara-1.0.0.zip").exists()


def test_build_release_refuses_a_binary_member(tmp_path):
    repo = git_repo(tmp_path)
    for rel, content in MANIFESTS.items():
        _write(repo, rel, content)
    # The version is read from plugin.json, so the binary goes in another
    # packaged manifest.
    (repo / "plugins" / "tara" / ".claude-plugin" / "plugin.json").write_bytes(
        b"\xff\xfe"
    )
    commit_all(repo)
    with pytest.raises(common.ResidueError):
        package.build_release(repo, repo / "dist")


def test_build_release_refuses_a_symlinked_parent_directory(tmp_path):
    # A symlinked *parent* directory would package files from outside the
    # checkout. Every path component must be checked, not only the last one.
    repo = git_repo(tmp_path / "repo")
    for rel, content in MANIFESTS.items():
        _write(repo, rel, content)
    commit_all(repo)

    outside = tmp_path / "outside"
    _write(outside, "plugin.json", '{"name": "tara", "version": "9.9.9"}\n')
    shutil.rmtree(repo / "plugins" / "tara")
    (repo / "plugins" / "tara").symlink_to(outside)

    with pytest.raises(common.PackagingError):
        package.build_release(repo, repo / "dist")
