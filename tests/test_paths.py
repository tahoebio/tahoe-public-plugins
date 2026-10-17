"""Repository layout, the shipped endpoint, and the install docs."""

from scripts import common


def test_required_layout_paths_exist():
    missing = [
        rel for rel in common.REQUIRED_LAYOUT if not (common.REPO_ROOT / rel).exists()
    ]
    assert missing == []


def test_plugin_root_keeps_expected_directories():
    for rel in ("assets", ".claude-plugin"):
        assert (common.plugin_dir() / rel).is_dir()


def test_mcp_config_points_at_the_public_host():
    # The host exists, so the plugin ships an active server configuration. It
    # must point only at the approved public endpoint — never a stand-in host.
    config = common.load_json(common.REPO_ROOT / common.MCP_CONFIG_REL)
    assert config["mcpServers"][common.MCP_SERVER_NAME]["url"] == common.MCP_ENDPOINT


def test_install_docs_link_to_canonical_procedure_and_keep_ownership_notes():
    install = (common.REPO_ROOT / "docs" / "install.md").read_text()
    assert "https://tara.tahoebio.io/install.md" in install
    assert "plugin-owned" in install
    assert "direct server entry" in install
    assert "advanced" in install.lower()
    readme = (common.REPO_ROOT / "README.md").read_text()
    assert "https://tara.tahoebio.io/install.md" in readme
    assert "docs/install.md" in readme


def test_compatibility_claims_only_codex_and_claude():
    compatibility = (common.REPO_ROOT / "docs" / "compatibility.md").read_text().lower()
    assert "codex" in compatibility
    assert "claude" in compatibility
    assert "not claimed" in compatibility


def test_compatibility_table_names_the_minimum_server_version():
    compatibility = (common.REPO_ROOT / "docs" / "compatibility.md").read_text()
    manifest = common.load_json(common.REPO_ROOT / common.PLUGIN_MANIFEST_REL)
    assert common.min_server_version(manifest) in compatibility
