"""Version consistency: one metadata authority, mirrored where it must be."""

from scripts import common


def _plugin_version() -> str:
    return common.load_json(common.plugin_dir() / "plugin.json")["version"]


def _min_server_version(rel: str) -> str | None:
    return common.min_server_version(common.load_json(common.REPO_ROOT / rel))


def test_both_manifests_declare_the_same_minimum_server_version():
    # Both hosts must read the same floor: a host that saw a different value
    # would warn (or not) inconsistently for the same server.
    portable = _min_server_version(common.PLUGIN_MANIFEST_REL)
    claude = _min_server_version(common.CLAUDE_ADAPTER_REL)
    assert portable is not None, "the portable manifest declares no minimum server version"
    assert portable == claude


def test_plugin_version_is_semver():
    assert common.SEMVER.match(_plugin_version())


def test_tooling_version_matches_plugin_version():
    assert common.pyproject_version() == _plugin_version()


def test_version_is_recorded_in_changelog():
    changelog = (common.REPO_ROOT / "CHANGELOG.md").read_text()
    assert _plugin_version() in changelog
