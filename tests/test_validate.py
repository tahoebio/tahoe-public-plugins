"""Negative coverage for the validators: bad input must be rejected."""

import json

import pytest

from helpers import commit_all, git_repo, shallow_clone
from scripts import common, validate


def _write(root, rel, payload):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _real(rel: str) -> dict:
    return common.load_json(common.REPO_ROOT / rel)


@pytest.fixture
def root(tmp_path):
    _write(tmp_path, common.PLUGIN_MANIFEST_REL, _real(common.PLUGIN_MANIFEST_REL))
    _write(tmp_path, common.CLAUDE_ADAPTER_REL, _real(common.CLAUDE_ADAPTER_REL))
    for rel in common.MARKETPLACE_PATHS:
        _write(tmp_path, rel, _real(rel))
    return tmp_path


def test_valid_root_passes(root):
    validate.validate_manifests(root)


def test_rejects_licence_field(root):
    manifest = _real(common.PLUGIN_MANIFEST_REL)
    manifest["license"] = "MIT"
    _write(root, common.PLUGIN_MANIFEST_REL, manifest)
    with pytest.raises(common.RepoError):
        validate.validate_manifests(root)


def test_rejects_wrong_plugin_name(root):
    manifest = _real(common.PLUGIN_MANIFEST_REL)
    manifest["name"] = "not-the-plugin"
    _write(root, common.PLUGIN_MANIFEST_REL, manifest)
    with pytest.raises(common.RepoError):
        validate.validate_manifests(root)


def test_rejects_version_on_catalog_entry(root):
    catalog = _real(common.CODEX_CATALOG_REL)
    catalog["plugins"][0]["version"] = "1.2.3"
    _write(root, common.CODEX_CATALOG_REL, catalog)
    with pytest.raises(common.RepoError):
        validate.validate_manifests(root)


def test_rejects_claude_catalog_without_an_owner(root):
    catalog = _real(common.CLAUDE_CATALOG_REL)
    del catalog["owner"]
    _write(root, common.CLAUDE_CATALOG_REL, catalog)
    with pytest.raises(common.RepoError):
        validate.validate_manifests(root)


def test_rejects_catalogs_disagreeing_on_source(root):
    # The two catalogs have different shapes but must agree on identity/source.
    catalog = _real(common.CLAUDE_CATALOG_REL)
    catalog["plugins"][0]["source"] = "./plugins/elsewhere"
    _write(root, common.CLAUDE_CATALOG_REL, catalog)
    with pytest.raises(common.RepoError):
        validate.validate_manifests(root)


def test_rejects_source_path_escaping_root(root):
    catalog = _real(common.CODEX_CATALOG_REL)
    catalog["plugins"][0]["source"] = "./../outside"
    _write(root, common.CODEX_CATALOG_REL, catalog)
    with pytest.raises(common.RepoError):
        validate.validate_manifests(root)


def test_rejects_claude_adapter_with_the_wrong_endpoint(root):
    adapter = _real(common.CLAUDE_ADAPTER_REL)
    adapter["mcpServers"][common.MCP_SERVER_NAME]["url"] = "https://example.com/mcp"
    _write(root, common.CLAUDE_ADAPTER_REL, adapter)
    with pytest.raises(common.RepoError):
        validate.validate_manifests(root)


def test_rejects_missing_layout_path(tmp_path):
    with pytest.raises(common.RepoError):
        validate.validate_layout(tmp_path)


def test_accepts_the_real_mcp_config(root):
    _write(root, common.MCP_CONFIG_REL, _real(common.MCP_CONFIG_REL))
    validate.validate_mcp_config(root)


def test_rejects_wrong_mcp_server_name(root):
    config = _real(common.MCP_CONFIG_REL)
    config["mcpServers"] = {"tara": config["mcpServers"][common.MCP_SERVER_NAME]}
    _write(root, common.MCP_CONFIG_REL, config)
    with pytest.raises(common.RepoError):
        validate.validate_mcp_config(root)


def test_rejects_wrong_mcp_endpoint(root):
    config = _real(common.MCP_CONFIG_REL)
    config["mcpServers"][common.MCP_SERVER_NAME]["url"] = "https://example.com/mcp"
    _write(root, common.MCP_CONFIG_REL, config)
    with pytest.raises(common.RepoError):
        validate.validate_mcp_config(root)


def test_rejects_mcp_credentials(root):
    config = _real(common.MCP_CONFIG_REL)
    config["mcpServers"][common.MCP_SERVER_NAME]["headers"] = {
        "Authorization": "Bearer example"
    }
    _write(root, common.MCP_CONFIG_REL, config)
    with pytest.raises(common.RepoError):
        validate.validate_mcp_config(root)


def test_rejects_version_mismatch(tmp_path):
    _write(
        tmp_path,
        common.PLUGIN_MANIFEST_REL,
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


def test_rejects_a_root_with_no_history(tmp_path):
    # A scan that cannot read history must fail, not report clean.
    with pytest.raises(common.RepoError):
        validate.validate_residue(tmp_path)


def test_rejects_shallow_history(tmp_path):
    source = git_repo(tmp_path / "source")
    (source / "note.md").write_text("hello\n")
    commit_all(source)
    shallow = shallow_clone(source, tmp_path / "shallow")
    with pytest.raises(common.RepoError):
        validate.validate_residue(shallow)


def test_real_repo_passes_validation():
    validate.validate_all(common.REPO_ROOT)
