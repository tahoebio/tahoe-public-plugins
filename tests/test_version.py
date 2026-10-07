"""Version consistency: one metadata authority, mirrored where it must be."""

from scripts import common


def _plugin_version() -> str:
    return common.load_json(common.plugin_dir() / "plugin.json")["version"]


def test_plugin_version_is_semver():
    assert common.SEMVER.match(_plugin_version())


def test_tooling_version_matches_plugin_version():
    assert common.pyproject_version() == _plugin_version()


def test_version_is_recorded_in_changelog():
    changelog = (common.REPO_ROOT / "CHANGELOG.md").read_text()
    assert _plugin_version() in changelog
