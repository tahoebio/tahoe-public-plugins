"""Manifest, schema and path rules for the marketplace catalog and the plugin.

Field names are taken from the Agent Plugins 1.0.0 schemas and the build docs
recorded in ``schemas/provenance.json``. No field is invented here.
"""

import pytest
from jsonschema import Draft202012Validator

from scripts import common


def _plugin_manifest() -> dict:
    return common.load_json(common.plugin_dir() / "plugin.json")


def test_plugin_manifest_validates_against_official_schema():
    schema = common.load_schema("plugin")
    Draft202012Validator(schema).validate(_plugin_manifest())


def test_plugin_identity_is_the_catalog_plugin():
    manifest = _plugin_manifest()
    assert manifest["name"] == common.PLUGIN_NAME
    assert isinstance(manifest["version"], str) and manifest["version"]


def test_plugin_manifest_carries_no_licence_field():
    # Licensing is unresolved; the schema allows omitting `license` and we must
    # not silently choose one.
    assert "license" not in _plugin_manifest()


@pytest.mark.parametrize("rel_path", common.MARKETPLACE_PATHS)
def test_marketplace_catalog_fields(rel_path):
    catalog = common.load_json(common.REPO_ROOT / rel_path)
    assert catalog["name"] == common.MARKETPLACE_NAME
    assert catalog["interface"]["displayName"] == common.MARKETPLACE_DISPLAY_NAME

    entries = catalog["plugins"]
    assert [entry["name"] for entry in entries] == [common.PLUGIN_NAME]

    entry = entries[0]
    # The docs instruct including all three on every entry.
    assert entry["policy"]["installation"] in common.INSTALLATION_POLICIES
    assert entry["policy"]["authentication"]
    assert entry["category"]


def test_marketplace_legacy_mirror_matches_canonical():
    canonical = common.load_json(common.REPO_ROOT / common.MARKETPLACE_PATHS[0])
    legacy = common.load_json(common.REPO_ROOT / common.MARKETPLACE_PATHS[1])
    assert canonical == legacy


def test_marketplace_source_path_is_relative_and_inside_root():
    catalog = common.load_json(common.REPO_ROOT / common.MARKETPLACE_PATHS[0])
    source = catalog["plugins"][0]["source"]
    path = source["path"] if isinstance(source, dict) else source
    assert isinstance(path, str)
    assert path.startswith("./")
    resolved = (common.REPO_ROOT / path).resolve()
    assert resolved == common.plugin_dir().resolve()
    assert resolved.is_relative_to(common.REPO_ROOT.resolve())


def test_marketplace_entry_has_no_version_single_metadata_authority():
    catalog = common.load_json(common.REPO_ROOT / common.MARKETPLACE_PATHS[0])
    assert "version" not in catalog["plugins"][0]


def test_skill_placeholder_is_marked_draft():
    skill = (common.plugin_dir() / "skills" / common.PLUGIN_NAME / "SKILL.md").read_text()
    lowered = skill.lower()
    assert "draft" in lowered
    assert "science review pending" in lowered
