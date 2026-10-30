"""Offline contract tests. These do not execute a host or establish live readiness."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess

import pytest

from scripts import common
from scripts import tool_examples as examples

ROOT = common.REPO_ROOT
CONTRACT = common.load_json(ROOT / examples.CONTRACT_REL)
FIXTURES = common.load_json(ROOT / examples.EXAMPLES_REL)


def request(tool="get_expression_slice", **arguments):
    return {"tool": tool, "arguments": arguments}


def context(name="emerald_visible"):
    return copy.deepcopy(FIXTURES["contexts"][name])


def documentation_root(tmp_path):
    """Assemble a small documentation fixture; no tool or agent is executed."""
    for rel in (examples.CONTRACT_REL, examples.EXAMPLES_REL):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, tmp_path / rel)
    for rel in common.SKILL_FILES:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("")
    calls = [
        {"tool": case["tool"], "arguments": case["arguments"]}
        for case in FIXTURES["cases"]
        if case["context"] == "emerald_visible"
        and case["expected_route"] == "send"
        and case["arguments"].get("dataset") == examples.EMERALD
    ]
    rel = next(rel for rel in common.SKILL_FILES if rel.endswith("tool-routing.md"))
    path = tmp_path / rel
    path.write_text(
        '## Worked calls\n```text\nget_expression_slice(genes=["TP53"])\n```\n'
        + "## Emerald Bay worked calls\n```json\n"
        + json.dumps(calls)
        + "\n```\n## Response contract\n"
    )
    return path


@pytest.mark.parametrize("case", FIXTURES["cases"], ids=lambda case: case["id"])
def test_declared_example_against_schema_and_routing_requirements(case):
    assert (
        examples.route(
            CONTRACT,
            FIXTURES["contexts"][case["context"]],
            request(case["tool"], **case["arguments"]),
        )
        == case["expected_route"]
    )


def test_fixture_validation_and_actual_shipped_calls():
    # This parses the shipped Markdown, so a disconnected valid JSON fixture
    # cannot hide an invalid worked call in the installed skill.
    calls = examples.validate_shipped_calls(ROOT)
    assert len(calls) >= 20
    assert {call["tool"] for call in calls} == common.PINNED_PUBLIC_TOOLS


@pytest.mark.parametrize(
    "version,expected",
    [
        ("0.3.10", "server_too_old"),
        ("0.4.0", "send"),
        ("0.10.0", "send"),
        (None, "compatibility_unknown"),
        ("unknown", "compatibility_unknown"),
        ("0.4", "compatibility_unknown"),
        ("0.4.0-beta", "compatibility_unknown"),
    ],
)
def test_feature_version_is_numeric_and_fails_closed(version, expected):
    ctx = context()
    ctx["server_version"] = version
    assert (
        examples.route(CONTRACT, ctx, request("get_guide", dataset=examples.EMERALD))
        == expected
    )


PANEL_CALLS = (
    request("get_validated_signatures", process="mTORC1"),
    request("get_pathway_scores", process="mTORC1", drug=["Trametinib"]),
    request(
        "get_pathway_scores",
        dataset=examples.EMERALD,
        process="mTORC1",
        samples=["<sample from search_conditions>"],
    ),
    request("get_guide", topic="validated-signatures"),
)


@pytest.mark.parametrize(
    "version,expected",
    [
        ("0.4.2", "server_too_old"),
        ("0.4.10", "server_too_old"),
        ("0.5.0", "send"),
        ("0.10.0", "send"),
        (None, "compatibility_unknown"),
        ("0.5", "compatibility_unknown"),
    ],
)
@pytest.mark.parametrize("call", PANEL_CALLS, ids=lambda call: call["tool"])
def test_panel_version_is_numeric_and_fails_closed(version, expected, call):
    ctx = context("signatures_visible")
    ctx["server_version"] = version
    assert examples.route(CONTRACT, ctx, call) == expected


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"advertised_signatures": None}, "signatures_unavailable"),
        ({"advertised_signatures": {}}, "signatures_unavailable"),
        ({"advertised_signatures": "tahoe-signatures/v02"}, "signatures_unavailable"),
        (
            {"advertised_signatures": {"release": "tahoe-signatures/v99"}},
            "signatures_unavailable",
        ),
        ({"discovery_ok": False}, "discovery_incomplete"),
        ({"discovery_truncated": True}, "discovery_incomplete"),
        ({"discovery_truncated": None}, "discovery_incomplete"),
    ],
)
@pytest.mark.parametrize("call", PANEL_CALLS, ids=lambda call: call["tool"])
def test_panel_requires_complete_discovery_at_the_snapshot_release(
    change, expected, call
):
    ctx = context("signatures_visible")
    ctx.update(change)
    assert examples.route(CONTRACT, ctx, call) == expected


def test_panel_gate_leaves_named_gene_set_calls_and_other_topics_alone():
    # An explicit gene-set request is legacy behavior on every server version;
    # only `process` and the lookup tool need the panel.
    legacy = request(
        "get_pathway_scores", gene_sets=["HALLMARK_MTORC1_SIGNALING"], drug=["Trametinib"]
    )
    assert examples.route(CONTRACT, context("tahoe_legacy"), legacy) == "send"
    explicit_null = request(
        "get_pathway_scores",
        process=None,
        gene_sets=["HALLMARK_MTORC1_SIGNALING"],
        drug=["Trametinib"],
    )
    assert examples.route(CONTRACT, context("tahoe_legacy"), explicit_null) == "send"
    # Panel visibility admits the panel's own topic, never an unrelated one.
    assert (
        examples.route(
            CONTRACT,
            context("signatures_visible"),
            request("get_guide", dataset=examples.EMERALD, topic="reading-expression"),
        )
        == "unsupported_topic"
    )


def test_documentation_panel_calls_route_through_the_panel_context(tmp_path):
    path = documentation_root(tmp_path)
    path.write_text(
        path.read_text()
        + '\n```json\n{"tool":"get_validated_signatures","arguments":{"process":"mTORC1"}}\n```\n'
        + '\n```json\n{"tool":"get_pathway_scores","arguments":{"process":"mTORC1","drug":["Trametinib"]}}\n```\n'
    )
    calls = examples.validate_shipped_calls(tmp_path)
    panel_calls = [call for call in calls if examples.uses_signatures(CONTRACT, call)]
    assert [call["tool"] for call in panel_calls] == [
        "get_validated_signatures",
        "get_pathway_scores",
    ]
    # The legacy Tahoe context predates the panel, so routing these through it
    # would fail; the shipped-call check must pick the panel context instead.
    for call in panel_calls:
        assert (
            examples.route(CONTRACT, context("tahoe_legacy"), call)
            == "server_too_old"
        )


@pytest.mark.parametrize("field", examples.DISCOVERY_LISTS)
def test_every_discovery_capability_field_is_required(field):
    ctx = context()
    del ctx["advertised_capabilities"][examples.EMERALD][field]
    assert (
        examples.route(CONTRACT, ctx, request("get_guide", dataset=examples.EMERALD))
        == "discovery_incomplete"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("discovery_ok", False),
        ("discovery_ok", None),
        ("discovery_truncated", True),
        ("discovery_truncated", None),
    ],
)
def test_failed_or_incomplete_discovery_never_authorizes_emerald(field, value):
    ctx = context()
    ctx[field] = value
    assert (
        examples.route(CONTRACT, ctx, request("get_guide", dataset=examples.EMERALD))
        == "discovery_incomplete"
    )


def test_release_mismatch_and_malformed_capabilities_are_not_success():
    for change in (
        {"release": "emerald-bay/future"},
        {"tools": "get_guide"},
        {"tools": [None]},
    ):
        ctx = context()
        ctx["advertised_capabilities"][examples.EMERALD].update(change)
        assert (
            examples.route(
                CONTRACT, ctx, request("get_guide", dataset=examples.EMERALD)
            )
            == "discovery_incomplete"
        )


@pytest.mark.parametrize(
    "tool", sorted(set(CONTRACT["datasets"][examples.EMERALD]["tools"]))
)
def test_each_emerald_tool_must_be_advertised_for_current_caller(tool):
    ctx = context()
    ctx["advertised_capabilities"][examples.EMERALD]["tools"].remove(tool)
    case = next(
        case
        for case in FIXTURES["cases"]
        if case["tool"] == tool
        and case["expected_route"] == "send"
        and case["arguments"].get("dataset") == examples.EMERALD
    )
    assert (
        examples.route(CONTRACT, ctx, request(tool, **case["arguments"]))
        == "unsupported_tool"
    )


@pytest.mark.parametrize("measurement", ["raw_counts", "cpm", "cpm_log1p"])
def test_each_requested_measurement_must_be_advertised(measurement):
    ctx = context()
    ctx["advertised_capabilities"][examples.EMERALD]["expression_measurements"].remove(
        measurement
    )
    assert (
        examples.route(
            CONTRACT,
            ctx,
            request(dataset=examples.EMERALD, genes=["TP53"], measurement=measurement),
        )
        == "unsupported_measurement"
    )


def test_absent_differential_or_growth_capability_cannot_fall_back():
    ctx = context()
    ctx["advertised_capabilities"][examples.EMERALD]["pathway_score_kinds"] = []
    ctx["advertised_capabilities"][examples.EMERALD]["phenotype_measurements"] = []
    assert (
        examples.route(
            CONTRACT,
            ctx,
            request(
                "get_pathway_scores",
                dataset=examples.EMERALD,
                gene_sets=["HALLMARK_P53_PATHWAY"],
                samples=["<selected sample>"],
            ),
        )
        == "unsupported_score_kind"
    )
    assert (
        examples.route(
            CONTRACT,
            ctx,
            request(
                "get_phenotype_scores",
                dataset=examples.EMERALD,
                phenotypes=["survival"],
            ),
        )
        == "unsupported_measurement"
    )


@pytest.mark.parametrize(
    "tool,arguments",
    [
        ("search_conditions", {"dose": 1}),
        ("list_cell_lines", {"organ": "Lung"}),
        ("get_drug_info", {"moa": "kinase inhibitor"}),
        ("get_drug_info", {"target": "TP53"}),
        ("get_phenotype_scores", {"dose": 1}),
        ("get_pathway_scores", {"dose": 1}),
    ],
)
def test_tahoe_only_filters_are_not_reinterpreted_for_emerald(tool, arguments):
    assert (
        examples.route(
            CONTRACT, context(), request(tool, dataset=examples.EMERALD, **arguments)
        )
        == "unsupported_filter"
    )


@pytest.mark.parametrize("tool,fields", examples.EMERALD_ARGUMENTS.items())
def test_emerald_only_arguments_are_never_sent_to_tahoe(tool, fields):
    for field in fields:
        schema = CONTRACT["tools"][tool]["properties"][field]
        argument = (
            1
            if field == "limit"
            else ("differential" if field == "score_kind" else ["<selected identity>"])
        )
        call = request(tool, **{field: argument})
        assert not examples.schema_problems(CONTRACT, call), schema
        assert examples.route(CONTRACT, context(), call) == "unsupported_argument"
        assert (
            examples.route(CONTRACT, context("tahoe_legacy"), call)
            == "unsupported_argument"
        )


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        {"tool": []},
        {"tool": [], "arguments": {}},
        {"tool": "health", "arguments": [], "extra": 1},
    ],
)
def test_malformed_call_is_an_error_not_a_crash(bad):
    assert examples.schema_problems(CONTRACT, bad)


def test_schema_does_not_coerce_strings_or_accept_invented_arguments():
    assert examples.schema_problems(
        CONTRACT,
        request(
            dataset=examples.EMERALD, genes=["TP53"], include_matched_controls="true"
        ),
    )
    assert examples.schema_problems(
        CONTRACT,
        request(dataset=examples.EMERALD, genes=["TP53"], normalization="DESeq2"),
    )
    assert examples.schema_problems(
        CONTRACT,
        request(
            "run_sql",
            statement="SELECT gene_name FROM gene_metadata LIMIT 1",
            max_rows="1",
        ),
    )


def test_json_parser_rejects_invalid_and_mixed_calls():
    with pytest.raises(common.RepoError, match="invalid JSON"):
        examples.fenced_calls('```json\n{"tool":}\n```\n')
    with pytest.raises(common.RepoError, match="mixed"):
        examples.fenced_calls('```json\n[{"tool":"health","arguments":{}}, 1]\n```\n')
    assert examples.fenced_calls('```json\n{"unrelated":"data"}\n```\n') == []


def test_legacy_parser_handles_literals_without_executing_python(tmp_path):
    calls = examples.legacy_calls(
        '```text\nget_expression_slice(genes=["TP53"], include_matched_controls=true)\nsend_feedback(text="test", useful=false)\n```\n'
    )
    assert calls[0]["arguments"]["include_matched_controls"] is True
    assert calls[1]["arguments"]["useful"] is False
    sentinel = tmp_path / "must-not-exist"
    malicious = f'```text\nhealth()\n__import__("pathlib").Path({str(sentinel)!r}).write_text("bad")\n```\n'
    with pytest.raises(common.RepoError, match="literal named arguments"):
        examples.legacy_calls(malicious)
    assert not sentinel.exists()


def test_documentation_validator_reads_each_call_and_explicit_emerald_dataset(tmp_path):
    path = documentation_root(tmp_path)
    assert examples.validate_shipped_calls(tmp_path)
    # Keep other complete Emerald examples, so aggregate coverage cannot conceal
    # a single omitted dataset in a valid get_guide call.
    path.write_text(
        path.read_text().replace(
            '"dataset": "emerald-bay"', '"dataset": "tahoe-100m"', 1
        )
    )
    with pytest.raises(common.RepoError, match="every Emerald worked call"):
        examples.validate_shipped_calls(tmp_path)


def test_documentation_invalid_argument_fails_even_with_full_fixture_coverage(tmp_path):
    path = documentation_root(tmp_path)
    path.write_text(
        path.read_text()
        + '\n```json\n{"tool":"resolve_genes","arguments":{"genes":23}}\n```\n'
    )
    with pytest.raises(common.RepoError, match="invalid_arguments"):
        examples.validate_shipped_calls(tmp_path)


def test_documentation_coverage_requires_all_three_expression_measurements(tmp_path):
    path = documentation_root(tmp_path)
    path.write_text(
        path.read_text().replace('"measurement": "cpm"', '"measurement": "cpm_log1p"')
    )
    with pytest.raises(common.RepoError, match="raw counts, CPM and log1p"):
        examples.validate_shipped_calls(tmp_path)


@pytest.mark.parametrize(
    "sql,max_rows",
    [
        ("DELETE FROM pb_pseudobulk", 1),
        ("SELECT * FROM pb_pseudobulk; SELECT * FROM pb_lattice", 1),
        ("SELECT * FROM gene_metadata LIMIT 1", 1),
        ("SELECT * FROM pb_pseudobulk LIMIT 1001", 1),
        ("SELECT * FROM pb_pseudobulk", 0),
        ("SELECT * FROM pb_pseudobulk", True),
    ],
)
def test_documentation_sql_is_bounded_and_dataset_scoped(sql, max_rows):
    assert not examples.sql_example_allowed(
        sql, CONTRACT["datasets"][examples.EMERALD]["tables"], max_rows
    )


def test_documentation_sql_uses_server_bound_and_ignores_placeholder_prose():
    sql = "SELECT sample FROM pb_pseudobulk WHERE sample = '<sample from search_conditions>'"
    assert examples.sql_example_allowed(
        sql, CONTRACT["datasets"][examples.EMERALD]["tables"], 5
    )


def test_new_fixtures_are_public_safe_and_never_packaged():
    paths = [
        examples.CONTRACT_REL,
        examples.EXAMPLES_REL,
        "scripts/tool_examples.py",
        "tests/test_tool_examples.py",
    ]
    for rel in paths:
        text = (ROOT / rel).read_text()
        assert common.scan_text(text) == [], rel
        if rel.endswith(".json"):
            assert common.locator_tokens(text) == [], rel
    members = common.collect_archive_members(ROOT, [*common.tracked_files(), *paths])
    assert set(members) == set(common.ARCHIVE_ALLOWLIST)
    assert not set(paths) & set(members)


def test_optional_candidate_requires_explicit_path_and_timeout_fails(
    monkeypatch, capsys
):
    assert examples.main(["--write-contract"]) == 1
    assert "requires an explicit local server root" in capsys.readouterr().err

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("offline candidate", 60)

    monkeypatch.setattr(examples, "candidate_contract", timeout)
    assert examples.main(["--server-root", "unused-local-candidate"]) == 1
    assert "validation failed" in capsys.readouterr().err


def test_phenotype_string_is_one_exact_name_not_a_comma_list():
    assert (
        examples.route(
            CONTRACT,
            context(),
            request(
                "get_phenotype_scores",
                dataset=examples.EMERALD,
                phenotypes="survival,growth_rate_released",
            ),
        )
        == "unsupported_measurement"
    )
