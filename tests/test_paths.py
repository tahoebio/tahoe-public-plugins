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


def test_install_docs_lead_with_the_plugin_marketplace_path():
    install = (common.REPO_ROOT / "docs" / "install.md").read_text()
    assert "codex plugin marketplace add tahoebio/tahoe-public-plugins" in install
    assert "codex plugin add tara@tahoe-public" in install
    assert "claude plugin marketplace add tahoebio/tahoe-public-plugins" in install
    assert "claude plugin install tara@tahoe-public" in install
    # The direct server add is documented only as an advanced fallback.
    assert "advanced" in install.lower()
    assert "codex mcp add tahoe-public --url https://tara.tahoebio.io/mcp" in install


def test_install_docs_state_signin_and_reload():
    install = (common.REPO_ROOT / "docs" / "install.md").read_text().lower()
    assert "sign-in" in install or "sign in" in install
    assert "reload" in install or "new session" in install


def test_compatibility_claims_only_codex_and_claude():
    compatibility = (common.REPO_ROOT / "docs" / "compatibility.md").read_text().lower()
    assert "codex" in compatibility
    assert "claude" in compatibility
    assert "not claimed" in compatibility
