"""The plugin payload: manifests for both hosts, and the tara skill.

The plugin ships connection manifests and one skill. The skill's data access
lives in its own text; the manifests carry no skills payload, and both hosts
discover ``skills/`` by convention (Claude Code and the Agent Plugins fixed
location both).
"""

from jsonschema import Draft202012Validator

from helpers import j
from scripts import common


def _config(rel: str) -> dict:
    return common.load_json(common.REPO_ROOT / rel)


def _skill_texts() -> dict[str, str]:
    return {
        rel: (common.REPO_ROOT / rel).read_text(encoding="utf-8")
        for rel in common.SKILL_FILES
    }


def test_the_skill_files_are_shipped_and_tracked():
    tracked = set(common.tracked_files())
    assert (common.REPO_ROOT / common.SKILL_MD_REL).is_file()
    for rel in common.SKILL_FILES:
        assert rel in tracked, rel


def test_frontmatter_names_the_skill_and_bounds_the_description():
    fields = common.parse_frontmatter(_skill_texts()[common.SKILL_MD_REL])
    assert fields.get("name") == common.PLUGIN_NAME
    description = fields.get("description", "")
    assert 1 <= len(description) <= common.SKILL_DESCRIPTION_MAX_CHARS


def test_skill_body_is_within_its_byte_budget():
    body = _skill_texts()[common.SKILL_MD_REL].encode("utf-8")
    assert len(body) <= common.SKILL_BODY_MAX_BYTES


def test_references_are_within_their_byte_budget():
    total = sum(len(body.encode("utf-8")) for body in _skill_texts().values())
    # SKILL.md is not a reference; the budget covers the three Tier 3 files.
    references = sum(
        len(_skill_texts()[rel].encode("utf-8")) for rel in common.REFERENCE_RELS
    )
    assert references <= common.REFERENCES_MAX_BYTES
    assert total >= references


def test_every_relative_link_resolves_inside_the_skill_dir():
    skill_dir = (common.REPO_ROOT / common.SKILL_DIR_REL).resolve()
    for rel, body in _skill_texts().items():
        for target in common.relative_links(body):
            resolved = (common.REPO_ROOT / rel).parent.joinpath(target).resolve()
            assert resolved.is_file(), f"{rel}: dangling link {target}"
            assert resolved.is_relative_to(skill_dir), f"{rel}: escapes skill dir"


def test_every_tool_the_skill_names_is_on_the_public_contract():
    known = common.known_tools()
    assert known, "the tool contract table must list the live tools"
    for rel, body in _skill_texts().items():
        for name in common.tool_shaped_mentions(body):
            assert name in known, f"{rel}: names a tool not on the contract: {name}"


def test_no_locator_path_or_cell_code_tokens_in_the_skill():
    for rel, body in _skill_texts().items():
        assert common.locator_tokens(body) == [], rel
        assert common.cell_code_tokens(body) == [], rel
        assert j("/Vol", "umes/") not in body, rel
        assert j("s3", "://") not in body, rel


def test_no_manifest_declares_a_skills_payload():
    # Both hosts discover ``skills/`` by convention; the field is neither needed
    # nor permitted by the portable schema (``additionalProperties: false``).
    manifest = _config(common.PLUGIN_MANIFEST_REL)
    Draft202012Validator(common.load_schema("plugin")).validate(manifest)
    assert manifest["name"] == common.PLUGIN_NAME
    assert "skills" not in manifest
    assert "license" not in manifest


def test_claude_native_adapter_declares_the_same_server_inline():
    adapter = _config(common.CLAUDE_ADAPTER_REL)
    assert adapter["name"] == common.PLUGIN_NAME
    servers = adapter["mcpServers"]
    assert list(servers) == [common.MCP_SERVER_NAME]
    server = servers[common.MCP_SERVER_NAME]
    assert server["type"] == "http"
    assert server["url"] == common.MCP_ENDPOINT
    assert "headers" not in server and "env" not in server


def test_codex_catalog_has_the_marketplace_shape():
    catalog = _config(common.CODEX_CATALOG_REL)
    assert catalog["name"] == common.MARKETPLACE_NAME
    assert catalog["interface"]["displayName"] == common.MARKETPLACE_DISPLAY_NAME
    entry = catalog["plugins"][0]
    assert [e["name"] for e in catalog["plugins"]] == [common.PLUGIN_NAME]
    assert entry["source"] == f"./{common.plugin_dir().relative_to(common.REPO_ROOT)}"
    assert entry["policy"]["installation"] in common.INSTALLATION_POLICIES
    assert entry["policy"]["authentication"]
    assert entry["category"]


def test_claude_catalog_has_its_own_shape_with_an_owner():
    catalog = _config(common.CLAUDE_CATALOG_REL)
    assert catalog["name"] == common.MARKETPLACE_NAME
    assert catalog["owner"]["name"]
    assert [e["name"] for e in catalog["plugins"]] == [common.PLUGIN_NAME]
    assert catalog["plugins"][0]["source"] == (
        f"./{common.plugin_dir().relative_to(common.REPO_ROOT)}"
    )


def test_catalogs_agree_on_identity_and_source():
    codex = _config(common.CODEX_CATALOG_REL)
    claude = _config(common.CLAUDE_CATALOG_REL)
    assert codex["name"] == claude["name"] == common.MARKETPLACE_NAME
    assert [e["name"] for e in codex["plugins"]] == [
        e["name"] for e in claude["plugins"]
    ]
    assert [e["source"] for e in codex["plugins"]] == [
        e["source"] for e in claude["plugins"]
    ]


def test_every_manifest_resolves_to_the_one_endpoint():
    portable = _config(common.MCP_CONFIG_REL)["mcpServers"][common.MCP_SERVER_NAME]
    native = _config(common.CLAUDE_ADAPTER_REL)["mcpServers"][common.MCP_SERVER_NAME]
    assert portable["url"] == native["url"] == common.MCP_ENDPOINT


def test_install_docs_describe_the_skill_payload():
    install = (common.REPO_ROOT / "docs" / "install.md").read_text(encoding="utf-8")
    assert "skills/tara/SKILL.md" in install
    assert "no guidance text" not in install


def test_release_archive_is_the_manifests_and_the_skill_files():
    members = common.collect_archive_members(common.REPO_ROOT, common.tracked_files())
    assert members == sorted(common.ARCHIVE_ALLOWLIST)
    assert common.CLAUDE_ADAPTER_REL in members
    assert common.SKILL_MD_REL in members
