"""The plugin payload: manifests for both hosts, and the tara skill.

The plugin ships connection manifests and one skill. The skill's data access
lives in its own text; the manifests carry no skills payload, and both hosts
discover ``skills/`` by convention (Claude Code and the Agent Plugins fixed
location both).
"""

import re

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


def test_every_tool_the_skill_names_is_known_or_marked_coming_soon():
    known = common.known_tools()
    planned = common.planned_tools()
    assert known, "the tool contract table must list the live tools"
    assert not (known & planned)
    for rel, body in _skill_texts().items():
        for name in common.tool_shaped_mentions(body):
            if name in known:
                continue
            assert name in planned, f"{rel}: names a tool not on the contract: {name}"
            assert common.names_coming_soon(body, name), (
                f"{rel}: {name} is not marked as not yet served"
            )


def test_the_sql_tool_is_declared_live():
    assert "run_sql" in common.known_tools()
    assert "run_sql" not in common.planned_tools()


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


# --- sync with the live public MCP (pinned tool list, SQL and VISION wording) ---


def test_the_contract_lists_exactly_the_pinned_live_tools():
    assert common.known_tools() == common.PINNED_PUBLIC_TOOLS


def test_every_pinned_tool_is_named_in_the_routing_reference():
    routing = (common.REPO_ROOT / common.SKILL_DIR_REL / "references" / "tool-routing.md")
    text = routing.read_text(encoding="utf-8")
    for name in sorted(common.PINNED_PUBLIC_TOOLS):
        assert f"`{name}" in text, name


def test_worked_cell_line_lookup_matches_the_cvcl_id_used_by_data_calls():
    routing = (common.REPO_ROOT / common.SKILL_DIR_REL / "references" / "tool-routing.md")
    text = routing.read_text(encoding="utf-8")
    assert 'list_cell_lines(query="A549")' in text
    assert 'list_cell_lines(organ="Lung")' in text
    worked_calls = text.split("## Worked calls", 1)[1].split("## Response contract", 1)[0]
    cell_arguments = []
    for line in worked_calls.splitlines():
        if "cell_lines=" in line or "cell_line=" in line:
            matches = re.findall(r'cell_lines?=\[?"([^"\]]+)"', line)
            assert matches, f"worked cell-line call has no quoted identifier: {line}"
            cell_arguments.extend(matches)
            assert all(identifier.startswith("CVCL_") for identifier in matches), line
    assert cell_arguments, "no worked data-tool call uses a cell-line identifier"
    assert set(cell_arguments) == {"CVCL_0023"}


def test_no_shipped_text_says_there_is_no_sql():
    surfaces = dict(_skill_texts())
    for rel in ("plugins/tara/plugin.json", "plugins/tara/.claude-plugin/plugin.json"):
        surfaces[rel] = (common.REPO_ROOT / rel).read_text(encoding="utf-8")
    for rel, text in surfaces.items():
        lowered = text.lower()
        assert "no sql" not in lowered, rel
        assert "there is no sql" not in lowered, rel
        assert "no client-supplied query text" not in lowered, rel


def test_table_semantics_are_served_by_get_guide_not_restated():
    refs = common.SKILL_DIR_REL + "/references/"
    sql = _skill_texts()[refs + "sql-guidance.md"]
    catalog = _skill_texts()[refs + "data-catalog.md"]
    assert 'get_guide(topic="table-reference")' in sql
    for heading in ("## Notes per table", "## The approved tables"):
        assert heading not in sql, heading
    for heading in ("## Genes", "## Expression grain and measurement", "## Working with the public files"):
        assert heading not in catalog, heading
    for rel, text in _skill_texts().items():
        lowered = text.lower()
        assert "centred duplicate" not in lowered, rel
        assert "tahoe-de-rhaister" not in lowered, rel


def test_host_descriptions_do_not_call_every_line_a_cancer_line():
    for rel in (
        common.SKILL_MD_REL,
        "plugins/tara/plugin.json",
    ):
        text = (common.REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "50 cancer cell lines" not in text, rel


def test_install_doc_counts_every_shipped_reference():
    install = (common.REPO_ROOT / "docs" / "install.md").read_text(encoding="utf-8")
    words = {3: "three", 4: "four", 5: "five"}
    assert f"{words[len(common.REFERENCE_RELS)]} references" in " ".join(install.split())


def test_skill_step_one_reads_the_server_version_and_warns_below_the_minimum():
    """Step 1 reads the served ``server_version`` and warns below the floor the
    plugin is frozen against, instead of assuming the frozen values hold."""
    body = " ".join(_skill_texts()[common.SKILL_MD_REL].split())
    minimum = common.min_server_version(_config(common.PLUGIN_MANIFEST_REL))
    assert minimum, "the manifest declares no minimum server version"
    assert "server_version" in body
    assert minimum in body
    assert "below that floor" in body
    assert "warn" in body.lower()


def test_skill_step_one_states_a_numeric_version_comparison():
    """A text comparison puts 0.3.10 below 0.3.9, so step 1 must say to compare
    the numbers; both versions are in the frozen record."""
    body = " ".join(_skill_texts()[common.SKILL_MD_REL].split())
    assert "numerically" in body
    assert "0.3.10 is newer than 0.3.9" in body


def test_skill_step_one_degrades_when_no_server_version_is_returned():
    """Neither endpoint yielding a version must read as unknown compatibility,
    never as the frozen values applying."""
    body = " ".join(_skill_texts()[common.SKILL_MD_REL].split()).lower()
    assert "try the other endpoint" in body
    assert "compatibility as unknown" in body


def test_out_of_scope_questions_get_an_in_scope_offer_and_no_outside_route():
    """A decline must not hint at routes beyond Tahoe's tools, and must offer
    the nearest analysis the served data can answer."""
    body = " ".join(_skill_texts()[common.SKILL_MD_REL].split()).lower()
    assert "offer the nearest analysis" in body
    assert "do not name, hint at or describe any route" in body


def test_unserved_rows_do_not_point_at_a_route_outside_the_tools():
    for rel, body in _skill_texts().items():
        lowered = " ".join(body.split()).lower()
        assert "see the public release" not in lowered, rel
        assert "hugging face" not in lowered, rel
