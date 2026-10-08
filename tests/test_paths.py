"""Repository layout, the shipped MCP endpoint, and the install docs."""

from scripts import common


def test_required_layout_paths_exist():
    missing = [rel for rel in common.REQUIRED_LAYOUT if not (common.REPO_ROOT / rel).exists()]
    assert missing == []


def test_plugin_root_keeps_expected_directories():
    for rel in ("skills", "assets"):
        assert (common.plugin_dir() / rel).is_dir()


def test_mcp_config_points_at_the_public_host():
    # The host exists, so the plugin ships an active server configuration. It
    # must point only at the approved public endpoint — never a stand-in host.
    config = common.load_json(common.REPO_ROOT / common.MCP_CONFIG_REL)
    assert config["mcpServers"][common.MCP_SERVER_NAME]["url"] == common.MCP_ENDPOINT


def test_install_docs_give_the_single_codex_command():
    install = (common.REPO_ROOT / "docs" / "install.md").read_text()
    assert (
        "codex mcp add tahoe-public --url https://tara.tahoebio.io/mcp" in install
    )
    assert "daemon" in install.lower()


def test_install_docs_claim_codex_as_the_only_tested_host():
    compatibility = (common.REPO_ROOT / "docs" / "compatibility.md").read_text().lower()
    assert "codex" in compatibility
    assert "not claimed" in compatibility


def test_skill_frontmatter_has_name_and_description():
    text = (common.plugin_dir() / "skills" / common.PLUGIN_NAME / "SKILL.md").read_text()
    assert text.startswith("---\n")
    frontmatter = text.split("---", 2)[1]
    fields = {
        line.split(":", 1)[0].strip()
        for line in frontmatter.splitlines()
        if ":" in line
    }
    assert {"name", "description"} <= fields
