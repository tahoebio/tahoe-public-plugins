"""The thin plugin: manifests for both hosts, and no guidance payload.

The plugin ships connection manifests only. Scientific guidance is served by the
service at runtime, not distributed as files here.
"""

from jsonschema import Draft202012Validator

from scripts import common


def _config(rel: str) -> dict:
    return common.load_json(common.REPO_ROOT / rel)


def test_no_skill_payload_is_shipped():
    assert not (common.plugin_dir() / "skills").exists()
    assert [rel for rel in common.tracked_files() if "/skills/" in rel] == []


def test_no_manifest_or_doc_points_at_a_skill_file():
    for rel in common.tracked_files():
        if not rel.endswith((".json", ".md")):
            continue
        text = (common.REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "SKILL.md" not in text, rel


def test_codex_manifest_is_the_portable_shape():
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
    assert catalog["plugins"][0]["source"] == f"./{common.plugin_dir().relative_to(common.REPO_ROOT)}"


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


def test_release_archive_is_exactly_the_manifest_files():
    members = common.collect_archive_members(common.REPO_ROOT, common.tracked_files())
    assert members == sorted(common.ARCHIVE_ALLOWLIST)
    assert common.CLAUDE_ADAPTER_REL in members
