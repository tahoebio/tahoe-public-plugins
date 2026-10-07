"""Repository layout and the "no active MCP config yet" guard."""

from scripts import common


def test_required_layout_paths_exist():
    missing = [rel for rel in common.REQUIRED_LAYOUT if not (common.REPO_ROOT / rel).exists()]
    assert missing == []


def test_plugin_root_keeps_expected_directories():
    for rel in ("skills", "assets"):
        assert (common.plugin_dir() / rel).is_dir()


def test_no_active_mcp_config_until_host_exists():
    # An mcp.json pointing at a stand-in host would let install "succeed"
    # against a service that does not exist. It must be absent until the host
    # is real; missing deployment config must fail clearly instead.
    assert not (common.plugin_dir() / "mcp.json").exists()


def test_install_docs_state_connection_is_pending():
    install = (common.REPO_ROOT / "docs" / "install.md").read_text().lower()
    assert "not yet" in install or "pending" in install
    assert "placeholder" not in install


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
