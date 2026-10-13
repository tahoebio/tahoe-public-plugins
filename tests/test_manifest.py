"""Manifest, schema and path rules for the plugin and the two catalogs.

Field names are taken from the Agent Plugins 1.0.0 schemas and the build docs
recorded in ``schemas/provenance.json``. No field is invented here.
"""

import pytest
from jsonschema import Draft202012Validator

from scripts import common


def _plugin_manifest() -> dict:
    return common.load_json(common.plugin_dir() / "plugin.json")


def test_plugin_manifest_validates_against_official_schema():
    Draft202012Validator(common.load_schema("plugin")).validate(_plugin_manifest())


def test_plugin_identity_is_the_catalog_plugin():
    manifest = _plugin_manifest()
    assert manifest["name"] == common.PLUGIN_NAME
    assert isinstance(manifest["version"], str) and manifest["version"]


def test_plugin_manifest_carries_no_licence_field():
    # Licensing is unresolved; the schema allows omitting `license` and we must
    # not silently choose one.
    assert "license" not in _plugin_manifest()


def test_plugin_manifest_declares_a_semver_minimum_server_version():
    # The plugin is frozen against a public server version; the manifest names
    # it so a host can warn on an older server. Field name is Tahoe's own
    # extension, so it must be semver.
    value = common.min_server_version(_plugin_manifest())
    assert isinstance(value, str) and common.SEMVER.match(value), value


@pytest.mark.parametrize("rel_path", common.MARKETPLACE_PATHS)
def test_marketplace_source_path_is_relative_and_inside_root(rel_path):
    catalog = common.load_json(common.REPO_ROOT / rel_path)
    for entry in catalog["plugins"]:
        path = entry["source"]
        assert isinstance(path, str) and path.startswith("./")
        resolved = (common.REPO_ROOT / path).resolve()
        assert resolved == common.plugin_dir().resolve()
        assert resolved.is_relative_to(common.REPO_ROOT.resolve())


@pytest.mark.parametrize("rel_path", common.MARKETPLACE_PATHS)
def test_marketplace_entry_has_no_version_single_metadata_authority(rel_path):
    catalog = common.load_json(common.REPO_ROOT / rel_path)
    assert "version" not in catalog["plugins"][0]
