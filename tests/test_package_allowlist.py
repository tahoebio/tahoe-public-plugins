"""Packaging: approved tracked files only, loud rejection of symlinks/hidden/generated."""

import pytest

from scripts import common


def _write(root, rel, content="x\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_collect_keeps_only_allowlisted_plugin_payload(tmp_path):
    rels = [
        "README.md",
        "docs/install.md",
        "plugins/tara/plugin.json",
        "plugins/tara/skills/tara/SKILL.md",
    ]
    for rel in rels:
        _write(tmp_path, rel)

    members = common.collect_archive_members(tmp_path, rels)
    assert members == [
        "plugins/tara/plugin.json",
        "plugins/tara/skills/tara/SKILL.md",
    ]


def test_reject_escaping_symlink(tmp_path):
    _write(tmp_path, "plugins/tara/plugin.json")
    link = tmp_path / "plugins" / "tara" / "escape"
    link.symlink_to(tmp_path / "README.md")

    with pytest.raises(common.PackagingError):
        common.collect_archive_members(
            tmp_path, ["plugins/tara/plugin.json", "plugins/tara/escape"]
        )


def test_reject_hidden_files(tmp_path):
    _write(tmp_path, "plugins/tara/.hidden")
    with pytest.raises(common.PackagingError):
        common.collect_archive_members(tmp_path, ["plugins/tara/.hidden"])


@pytest.mark.parametrize(
    "rel",
    [
        "plugins/tara/__pycache__/mod.cpython-311.pyc",
        "plugins/tara/bundle.zip",
        "plugins/tara/mod.pyc",
    ],
)
def test_reject_generated_output(tmp_path, rel):
    _write(tmp_path, rel)
    with pytest.raises(common.PackagingError):
        common.collect_archive_members(tmp_path, [rel])


def test_empty_selection_is_an_error(tmp_path):
    _write(tmp_path, "README.md")
    with pytest.raises(common.PackagingError):
        common.collect_archive_members(tmp_path, ["README.md"])


def test_archive_is_deterministic(tmp_path):
    _write(tmp_path, "plugins/tara/plugin.json", '{"name": "tara"}\n')
    _write(tmp_path, "plugins/tara/skills/tara/SKILL.md", "# skill\n")
    members = common.collect_archive_members(
        tmp_path, ["plugins/tara/plugin.json", "plugins/tara/skills/tara/SKILL.md"]
    )

    first = common.build_archive(tmp_path, members, tmp_path / "a.zip")
    second = common.build_archive(tmp_path, members, tmp_path / "b.zip")
    assert common.sha256_file(first) == common.sha256_file(second)
    assert first.read_bytes() == second.read_bytes()


def test_checksum_matches_archive(tmp_path):
    _write(tmp_path, "plugins/tara/plugin.json", '{"name": "tara"}\n')
    members = common.collect_archive_members(tmp_path, ["plugins/tara/plugin.json"])
    archive = common.build_archive(tmp_path, members, tmp_path / "tara.zip")

    checksum = common.write_checksum(archive)
    assert checksum.read_text().split()[0] == common.sha256_file(archive)


def test_repo_archive_is_exactly_the_plugin_payload():
    members = common.collect_archive_members(common.REPO_ROOT, common.tracked_files())
    assert members
    assert all(member.startswith(common.ARCHIVE_ALLOWLIST) for member in members)
