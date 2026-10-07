"""Negative coverage for the validators: bad input must be rejected."""

import json

import pytest

from scripts import common, validate


def _write(root, rel, payload):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _real_plugin_manifest() -> dict:
    return common.load_json(common.plugin_dir() / "plugin.json")


def _real_catalog() -> dict:
    return common.load_json(common.REPO_ROOT / common.MARKETPLACE_PATHS[0])


def _write_catalog(root, catalog):
    for rel in common.MARKETPLACE_PATHS:
        _write(root, rel, catalog)


@pytest.fixture
def root(tmp_path):
    _write(tmp_path, f"plugins/{common.PLUGIN_NAME}/plugin.json", _real_plugin_manifest())
    _write_catalog(tmp_path, _real_catalog())
    return tmp_path


def test_valid_root_passes(root):
    validate.validate_manifests(root)


def test_rejects_licence_field(root):
    manifest = _real_plugin_manifest()
    manifest["license"] = "MIT"
    _write(root, f"plugins/{common.PLUGIN_NAME}/plugin.json", manifest)
    with pytest.raises(common.RepoError):
        validate.validate_manifests(root)


def test_rejects_wrong_plugin_name(root):
    manifest = _real_plugin_manifest()
    manifest["name"] = "not-the-plugin"
    _write(root, f"plugins/{common.PLUGIN_NAME}/plugin.json", manifest)
    with pytest.raises(common.RepoError):
        validate.validate_manifests(root)


def test_rejects_version_on_catalog_entry(root):
    catalog = _real_catalog()
    catalog["plugins"][0]["version"] = "1.2.3"
    _write_catalog(root, catalog)
    with pytest.raises(common.RepoError):
        validate.validate_manifests(root)


def test_rejects_catalog_drift(root):
    catalog = _real_catalog()
    catalog["interface"]["displayName"] = "Something Else"
    _write(root, common.MARKETPLACE_PATHS[1], catalog)
    with pytest.raises(common.RepoError):
        validate.validate_manifests(root)


def test_rejects_source_path_escaping_root(root):
    catalog = _real_catalog()
    catalog["plugins"][0]["source"] = "./../outside"
    _write_catalog(root, catalog)
    with pytest.raises(common.RepoError):
        validate.validate_manifests(root)


def test_rejects_missing_layout_path(tmp_path):
    with pytest.raises(common.RepoError):
        validate.validate_layout(tmp_path)


def test_rejects_version_mismatch(tmp_path):
    _write(
        tmp_path,
        f"plugins/{common.PLUGIN_NAME}/plugin.json",
        {
            "$schema": common.load_schema("plugin")["$id"],
            "name": common.PLUGIN_NAME,
            "version": "9.9.9",
        },
    )
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "1.0.0"\n')
    (tmp_path / "CHANGELOG.md").write_text("## 9.9.9\n")
    with pytest.raises(common.RepoError):
        validate.validate_versions(tmp_path)


def test_real_repo_passes_validation():
    validate.validate_all(common.REPO_ROOT)
