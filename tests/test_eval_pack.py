"""Offline checks for the plugin eval pack. No runner and no network.

Synthetic recordings and transcripts are labelled as such. They are not
measurements and they are not evidence that a host session passed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from helpers import j
from scripts import common
from scripts.eval_cases import PENDING_CASES, all_specs, render_suite, write_suite
from scripts.eval_pack import (
    RECORDING_FORMAT,
    EvalError,
    case_tags,
    parse_frontmatter,
    record_from_aggregate,
    record_problems,
    retarget_plugin_copy,
    retarget_plugin_copy_local,
    scoped_mcp_tool,
    score_transcript,
)

S2 = "s2-apoptosis"
BLOCKED_EXAMPLE = "s1-mapk-trametinib"


@pytest.fixture(scope="module")
def suite(tmp_path_factory):
    dest = tmp_path_factory.mktemp("eval-suite")
    write_suite(dest)
    return dest


def _s2_calls(*, forbidden: bool) -> list[dict]:
    calls = [
        {"tool": "Skill", "input": {"skill": "tara"}},
        {"tool": scoped_mcp_tool("list_releases"), "input": {}},
        {"tool": scoped_mcp_tool("search_conditions"), "input": {"drug": "Trametinib"}},
        {
            "tool": scoped_mcp_tool("get_pathway_scores"),
            "input": {"process": "Apoptosis", "drug": ["Trametinib"]},
        },
    ]
    if forbidden:
        calls.append(
            {
                "tool": scoped_mcp_tool("run_sql"),
                "input": {"statement": "select 1", "max_rows": 1},
            }
        )
    return calls


def _score_s2(suite, *, forbidden: bool, message: str = "Apoptosis has no validated readout."):
    return score_transcript(
        suite / S2,
        {"calls": _s2_calls(forbidden=forbidden), "last_message": message},
    )


def test_suite_covers_the_public_prompts_except_pending_and_cancellation():
    names = {spec.name for spec in all_specs()}
    for number in range(1, 9):
        assert any(name.startswith(f"s{number}-") for name in names)
    for number in range(1, 6):
        assert any(name.startswith(f"e{number}-") for name in names)
    for number in range(1, 6):
        assert any(name.startswith(f"a{number}-") for name in names)
    for case_id in (f"EB{number:02d}" for number in range(1, 24)):
        present = case_id.lower() in names
        assert present is (case_id not in PENDING_CASES)
    assert "live-probe" in names
    assert len(names) == len(all_specs())


def test_rendering_into_a_temp_dir_writes_forty_cases(tmp_path):
    destination = write_suite(tmp_path / "evals")
    prompts = list(destination.glob("*/prompt.md"))
    assert len(prompts) == 40
    assert {path.parent.name for path in prompts} == {spec.name for spec in all_specs()}
    rendered = render_suite()
    on_disk = {
        path.relative_to(destination).as_posix(): path.read_text(encoding="utf-8")
        for path in destination.rglob("*")
        if path.is_file()
    }
    assert on_disk == rendered


_PLAIN_SAFE = re.compile(r"[A-Za-z0-9_-]+")


def _strict_scalar_ok(raw: str) -> bool:
    """True for a value a strict YAML loader reads as written: a JSON string,
    or a plain token with no YAML indicator characters."""
    if raw.startswith('"'):
        try:
            return isinstance(json.loads(raw), str)
        except ValueError:
            return False
    return _PLAIN_SAFE.fullmatch(raw) is not None


def test_every_rendered_prompt_frontmatter_is_strict_yaml(tmp_path):
    """The eval runner refuses a case whose frontmatter has a plain scalar such
    as ``Source: x`` (a second mapping indicator). Every value here is a JSON
    string, a plain token, or a flow list of those."""
    destination = write_suite(tmp_path / "evals")
    for prompt in sorted(destination.glob("*/prompt.md")):
        body = prompt.read_text(encoding="utf-8").split("---\n")[1]
        for line in body.splitlines():
            key, sep, raw = line.partition(": ")
            assert sep and _PLAIN_SAFE.fullmatch(key), (prompt.parent.name, line)
            if raw.startswith("[") and raw.endswith("]"):
                items = [item.strip() for item in raw[1:-1].split(",")]
                assert all(_strict_scalar_ok(item) for item in items), (prompt.parent.name, line)
            else:
                assert _strict_scalar_ok(raw), (prompt.parent.name, line)
        fields, _ = parse_frontmatter(prompt.read_text(encoding="utf-8"))
        assert fields["name"] == prompt.parent.name
        assert ": " in str(fields["description"])


def test_rendering_into_the_plugin_tree_is_refused_and_writes_nothing():
    dest = common.plugin_dir() / "evals"
    with pytest.raises(EvalError, match="plugins/"):
        write_suite(dest)
    assert not dest.exists()


def test_blocked_cases_are_tagged_and_named_in_the_readme(suite):
    readme = (suite / "README.md").read_text(encoding="utf-8")
    blocked = [spec for spec in all_specs() if spec.blocked_reason]
    assert blocked
    for spec in blocked:
        assert "blocked" in case_tags(suite / spec.name)
        assert "release" not in case_tags(suite / spec.name)
        assert f"`{spec.name}`" in readme
        assert spec.blocked_reason in readme
    assert "scripts/eval_replay.sh RUN_DIR/eval-recording RUN_DIR" in readme
    assert "--tag release" in readme
    assert "claude plugin eval" not in readme
    assert "not run" in readme
    assert "live profile is not added" in readme


def test_release_cases_are_not_tagged_blocked(suite):
    for spec in all_specs():
        if "release" in spec.tags:
            assert spec.blocked_reason is None
            assert "blocked" not in case_tags(suite / spec.name)


def test_every_case_has_rubric_hard_fail_regex_and_with_only_tool_graders(suite):
    for spec in all_specs():
        graders = suite / spec.name / "graders"
        rubric = (graders / "rubric.md").read_text(encoding="utf-8")
        assert "type: llm" in rubric
        assert "tool-less guess" in rubric
        assert 'NULL treated as "no effect" or zero' in rubric
        phrases = (graders / "hard-fail-phrases.md").read_text(encoding="utf-8")
        assert "match: not_contains" in phrases
        for path in graders.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            if "type: tool_used" in text or "type: tool_order" in text:
                assert "arm: with-only" in text, path.name


def test_pathway_process_grader_rejects_a_call_that_omits_process(suite):
    score = score_transcript(
        suite / S2,
        {
            "calls": [
                {
                    "tool": scoped_mcp_tool("get_pathway_scores"),
                    "input": {"gene_sets": ["OTHER"]},
                },
            ],
            "last_message": "No validated readout.",
        },
    )
    grader = next(item for item in score.graders if item.name == "use-get_pathway_scores")
    assert grader.passed is False
    source = (suite / S2 / "graders" / "use-get_pathway_scores.md").read_text(
        encoding="utf-8"
    )
    assert f"tool: {scoped_mcp_tool('get_pathway_scores')}" in source
    assert "process" in source
    assert "input_match:" in source


def test_forbidden_run_sql_scores_zero_while_required_graders_pass(suite):
    """max: 0 on run_sql fails the case even when the required tools matched."""
    score = _score_s2(suite, forbidden=True)
    by_name = {item.name: item for item in score.graders}
    assert by_name["forbid-run_sql"].passed is False
    assert "run_sql" in by_name["forbid-run_sql"].reason
    assert by_name["use-get_pathway_scores"].passed is True
    assert by_name["use-search_conditions"].passed is True
    assert by_name["hard-fail-phrases"].passed is True
    assert score.score == 0
    forbid = (suite / S2 / "graders" / "forbid-run_sql.md").read_text(encoding="utf-8")
    assert f"tool: {scoped_mcp_tool('run_sql')}" in forbid
    assert "\ntool: run_sql\n" not in forbid
    assert "max: 0" in forbid
    assert "min: 0" in forbid


def test_same_transcript_without_run_sql_is_not_scored_zero(suite):
    score = _score_s2(suite, forbidden=False)
    assert score.score == 1
    assert all(item.passed for item in score.graders if item.scored)


def test_hard_fail_phrase_in_the_answer_fails_that_grader(suite):
    score = _score_s2(suite, forbidden=False, message="The row treated the missing value as zero.")
    grader = next(item for item in score.graders if item.name == "hard-fail-phrases")
    assert grader.passed is False


def test_guide_before_phenotype_fails_when_the_score_call_is_first(suite):
    early = score_transcript(
        suite / "e3-bortezomib-survival",
        {
            "calls": [
                {
                    "tool": scoped_mcp_tool("get_phenotype_scores"),
                    "input": {"drug": ["Bortezomib"]},
                },
                {
                    "tool": scoped_mcp_tool("get_guide"),
                    "input": {"topic": "phenotype-readouts"},
                },
            ],
            "last_message": "Survival near zero is not no effect.",
        },
    )
    late = score_transcript(
        suite / "e3-bortezomib-survival",
        {
            "calls": [
                {
                    "tool": scoped_mcp_tool("get_guide"),
                    "input": {"topic": "phenotype-readouts"},
                },
                {
                    "tool": scoped_mcp_tool("get_phenotype_scores"),
                    "input": {"drug": ["Bortezomib"]},
                },
            ],
            "last_message": "Survival near zero is not no effect.",
        },
    )
    early_order = next(item for item in early.graders if item.name.startswith("order-"))
    late_order = next(item for item in late.graders if item.name.startswith("order-"))
    assert early_order.passed is False
    assert late_order.passed is True


def _record(status: str, *, partial: bool = False) -> dict:
    return {
        "schema_version": 1,
        "partial": partial,
        "partial_reason": "cost_ceiling" if partial else None,
        "passed": [BLOCKED_EXAMPLE] if status == "pass" else [],
        "cases": [
            {
                "name": BLOCKED_EXAMPLE,
                "status": status,
                "graders": [{"name": "rubric", "passed": status == "pass", "reason": "synthetic"}],
            }
        ],
    }


def test_record_marking_a_blocked_case_as_pass_is_refused():
    problems = record_problems(_record("pass"))
    assert any("blocked case counted as pass" in item for item in problems)
    assert record_problems(_record("blocked")) == []
    assert record_problems(_record("fail")) == []


def test_blocked_name_in_passed_is_refused_when_case_status_is_blocked():
    """The ``passed`` list is checked even when the case status is not pass."""
    record = _record("blocked")
    record["passed"] = [BLOCKED_EXAMPLE]
    problems = record_problems(record)
    assert f"{BLOCKED_EXAMPLE}: blocked case counted as pass" in problems


def test_blocked_case_status_pass_is_refused_when_name_is_not_in_passed():
    """A pass status is refused even when the name is absent from ``passed``."""
    record = _record("pass")
    record["passed"] = []
    problems = record_problems(record)
    assert f"{BLOCKED_EXAMPLE}: blocked case counted as pass" in problems


def test_partial_run_record_is_refused():
    problems = record_problems(_record("fail", partial=True))
    assert any(item.startswith("partial run") for item in problems)


def test_perfect_runner_score_on_a_blocked_case_is_not_a_pass():
    aggregate = {
        "partial": False,
        "claudeVersion": "synthetic",
        "cases": [
            {
                "name": BLOCKED_EXAMPLE,
                "aggregates": {"score": 1},
                "arms": {
                    "with": [
                        {
                            "graders": [
                                {
                                    "name": "rubric",
                                    "passed": True,
                                    "explanation": "synthetic judge",
                                }
                            ]
                        }
                    ]
                },
            }
        ],
    }
    record = record_from_aggregate(aggregate)
    case = record["cases"][0]
    assert case["status"] == "blocked"
    assert BLOCKED_EXAMPLE not in record["passed"]
    assert case["graders"][0]["reason"] == "synthetic judge"
    assert record_problems(record) == []


def test_partial_aggregate_stays_partial_in_the_record():
    record = record_from_aggregate(
        {"partial": True, "partialReason": "cost_ceiling", "cases": []}
    )
    assert record["partial"] is True
    assert record_problems(record)


def test_release_script_stages_a_temp_copy_and_passes_the_release_tag():
    text = (common.REPO_ROOT / "scripts" / "eval_replay.sh").read_text(encoding="utf-8")
    for flag in (
        "--tag release",
        "--ablation none",
        "--max-cost-usd",
        "--threshold 1.0",
        "--json",
    ):
        assert flag in text
    assert "eval_cases.py" in text
    assert "eval_proxy.py" in text
    assert "--mocks off" in text
    assert 'claude plugin eval "$WORK/plugin"' in text
    assert "plugins/tara/evals" not in text
    assert 'claude plugin eval "$ROOT/plugins/tara"' not in text
    assert "aggregate-result.json" in text
    assert "report.html" in text
    assert "check_evals.py" in text
    human = (common.REPO_ROOT / "evals" / "tara" / "README.md").read_text(encoding="utf-8")
    assert "scripts/eval_record.sh RUN_DIR" in human
    assert "scripts/eval_replay.sh RUN_DIR/eval-recording RUN_DIR" in human
    assert "claude plugin eval" not in human


def test_failing_runner_still_copies_results_and_exits_with_runner_code(tmp_path):
    """A runner exit of 1 does not skip the copy or the checker."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "claude"
    stub.write_text(
        "\n".join(
            (
                "#!/bin/sh",
                "output_dir=",
                "json_path=",
                "prev=",
                'for arg in "$@"; do',
                '  if [ "$prev" = "--output-dir" ]; then',
                "    output_dir=$arg",
                '  elif [ "$prev" = "--json" ]; then',
                "    json_path=$arg",
                "  fi",
                "  prev=$arg",
                "done",
                'mkdir -p "$output_dir"',
                "printf '%s\\n' '{\"partial\":false,\"cases\":[]}' > \"$output_dir/aggregate-result.json\"",
                "printf '%s\\n' '<html>synthetic report</html>' > \"$output_dir/report.html\"",
                "printf '%s\\n' '{\"partial\":false,\"cases\":[]}' > \"$json_path\"",
                "exit 1",
                "",
            )
        ),
        encoding="utf-8",
    )
    stub.chmod(0o755)
    recording = tmp_path / "recording"
    recording.mkdir()
    (recording / "responses.json").write_text(
        json.dumps(
            {
                "format": RECORDING_FORMAT,
                "initialize": {"protocolVersion": "synthetic"},
                "tools/list": {"tools": []},
                "calls": {},
                "conflicts": {},
                "disclosure_hits": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env.setdefault("UV_CACHE_DIR", "/tmp/uv-cache")
    completed = subprocess.run(
        [
            "sh",
            str(common.REPO_ROOT / "scripts" / "eval_replay.sh"),
            str(recording),
            str(run_dir),
        ],
        cwd=common.REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1, completed.stderr
    assert json.loads((run_dir / "eval-replay-aggregate-result.json").read_text(encoding="utf-8"))["cases"] == []
    assert "synthetic report" in (run_dir / "eval-replay-report.html").read_text(encoding="utf-8")
    assert json.loads((run_dir / "eval-replay-result.json").read_text(encoding="utf-8"))["partial"] is False
    assert (run_dir / "eval-replay-record.json").is_file()
    assert (run_dir / "eval-replay-misses.jsonl").is_file()
    assert not (common.plugin_dir() / "evals").exists()


_PUBLIC_HOST = "tara." + "tahoebio.io"


def _private_hosts(text: str) -> set[str]:
    """Company hosts other than the public service. None may appear in public files."""
    return set(re.findall(r"[a-z0-9-]+\.tahoebio\.io", text)) - {_PUBLIC_HOST}


def test_private_host_check_flags_any_company_host_but_the_public_one():
    assert _private_hosts("see https://" + _PUBLIC_HOST + "/mcp") == set()
    assert _private_hosts("https://internal-x." + "tahoebio.io/mcp") == {"internal-x." + "tahoebio.io"}


def test_probe_script_uses_mocks_off_and_does_not_name_a_stand_in_host():
    text = (common.REPO_ROOT / "scripts" / "eval_probe.sh").read_text(encoding="utf-8")
    assert "--mocks off" in text
    assert scoped_mcp_tool("*") in text
    assert "--case live-probe" in text
    assert "eval_cases.py" in text
    assert 'claude plugin eval "$WORK/plugin"' in text
    assert "plugins/tara/evals" not in text
    assert _private_hosts(text) == set()


def test_retarget_refuses_the_repository_plugin_and_updates_a_copy(tmp_path):
    original = (common.plugin_dir() / "mcp.json").read_text(encoding="utf-8")
    with pytest.raises(EvalError, match="repository plugin"):
        retarget_plugin_copy(
            common.plugin_dir(),
            "https://example.test/mcp",
            repo_plugin=common.plugin_dir(),
        )
    assert (common.plugin_dir() / "mcp.json").read_text(encoding="utf-8") == original

    copy = tmp_path / "plugin"
    (copy / ".claude-plugin").mkdir(parents=True)
    manifest = {
        "mcpServers": {
            "tahoe-public": {
                "type": "http",
                "url": "https://example.test/original",
                "headers": {"Authorization": "must-not-survive"},
            }
        }
    }
    for rel in ("mcp.json", ".claude-plugin/plugin.json"):
        (copy / rel).write_text(json.dumps(manifest), encoding="utf-8")
    retarget_plugin_copy(copy, "https://example.test/mcp", repo_plugin=common.plugin_dir())
    for rel in ("mcp.json", ".claude-plugin/plugin.json"):
        written = json.loads((copy / rel).read_text(encoding="utf-8"))
        server = written["mcpServers"]["tahoe-public"]
        assert server["url"] == "https://example.test/mcp"
        assert "headers" not in server
    assert (common.plugin_dir() / "mcp.json").read_text(encoding="utf-8") == original


def test_retarget_rejects_a_url_with_userinfo_without_writing(tmp_path):
    copy = tmp_path / "plugin"
    (copy / ".claude-plugin").mkdir(parents=True)
    body = json.dumps({"mcpServers": {"tahoe-public": {"type": "http", "url": "https://example.test/old"}}})
    for rel in ("mcp.json", ".claude-plugin/plugin.json"):
        (copy / rel).write_text(body, encoding="utf-8")
    with pytest.raises(EvalError):
        retarget_plugin_copy(
            copy,
            j("https://", "user:secret@", "example.test/mcp"),
            repo_plugin=common.plugin_dir(),
        )
    assert json.loads((copy / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]["tahoe-public"][
        "url"
    ] == "https://example.test/old"


def test_mcp_grader_name_matches_the_server_in_mcp_json(suite):
    """Graders use the plugin-scoped tool name; mock files keep the short name."""
    config = json.loads((common.plugin_dir() / "mcp.json").read_text(encoding="utf-8"))
    server = next(iter(config["mcpServers"]))
    assert server == common.MCP_SERVER_NAME
    expected = f"mcp__plugin_{common.PLUGIN_NAME}_{server}__get_pathway_scores"
    assert scoped_mcp_tool("get_pathway_scores") == expected
    grader = (suite / S2 / "graders" / "use-get_pathway_scores.md").read_text(encoding="utf-8")
    assert f"tool: {expected}\n" in grader
    order = (
        suite / "e3-bortezomib-survival" / "graders" / "order-get_guide-before-get_phenotype_scores.md"
    ).read_text(encoding="utf-8")
    assert f"before: {scoped_mcp_tool('get_guide')}" in order
    assert f"after: {scoped_mcp_tool('get_phenotype_scores')}" in order
    skill = (suite / S2 / "graders" / "skill.md").read_text(encoding="utf-8")
    assert "tool: Skill\n" in skill


def test_plugin_tree_has_no_eval_suite_after_the_tests():
    assert not (common.plugin_dir() / "evals").exists()


def test_new_eval_files_have_no_residue_or_issue_ids(suite):
    roots = [
        suite,
        common.REPO_ROOT / "scripts" / "eval_pack.py",
        common.REPO_ROOT / "scripts" / "eval_cases.py",
        common.REPO_ROOT / "scripts" / "eval_probe.py",
        common.REPO_ROOT / "scripts" / "eval_probe.sh",
        common.REPO_ROOT / "scripts" / "eval_replay.sh",
        common.REPO_ROOT / "scripts" / "eval_record.sh",
        common.REPO_ROOT / "scripts" / "eval_proxy.py",
        common.REPO_ROOT / "scripts" / "check_evals.py",
        common.REPO_ROOT / "evals" / "disclosure_allow.json",
    ]
    files: list[Path] = []
    for root in roots:
        if root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file())
        else:
            files.append(root)
    issue = j("ML", "-", "584")
    hits = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        # Locator tokens are a data-file check. Python attribute chains
        # (``sys.path.insert``) match the same shape and are not catalog names.
        locators = common.locator_tokens(text) if path.suffix != ".py" else []
        if common.scan_text(text) or common.cell_code_tokens(text) or locators:
            hits.append(str(path))
        if issue in text or _private_hosts(text) or "/Users/" in text:
            hits.append(str(path))
    assert hits == []


# --- SMILES shape exemption --------------------------------------------------

_TRAMETINIB_SMILES = "CN1C2=C(C(=C(C1=O)F)NC3=C(C=C(C=C3)I)F)C(=O)N(C=N2)CC(CO)O"


def _drug_table(column: str, value: str) -> dict:
    return {"columns": ["drug", column], "rows": [["Trametinib", value]], "ok": True}


def _allow():
    from scripts.eval_pack import load_disclosure_allowlist

    return load_disclosure_allowlist()


def test_smiles_in_the_canonical_smiles_column_is_exempt():
    """A real structure trips the notebook-code pattern; the committed shape entry
    exempts it in the canonical_smiles column of a columns+rows table."""
    from scripts.eval_pack import remaining_patterns, scan_text

    assert scan_text(_TRAMETINIB_SMILES) == ["internal_ref"]
    assert remaining_patterns(_drug_table("canonical_smiles", _TRAMETINIB_SMILES), _allow()) == []


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("notes", _TRAMETINIB_SMILES),
        ("canonical_smiles", "D" + "94"),
        ("canonical_smiles", "ABCD-" + "N12"),
        ("canonical_smiles", "CN1C2=C N2 " + "note" + "book"),
        ("canonical_smiles", "C" + "C(=O)" + "study_357"),
    ],
)
def test_internal_ref_outside_a_smiles_shaped_canonical_smiles_cell_still_hits(column, value):
    from scripts.eval_pack import remaining_patterns

    assert "internal_ref" in remaining_patterns(_drug_table(column, value), _allow())


def test_a_smiles_cell_that_also_names_the_atlas_still_hits():
    from scripts.eval_pack import remaining_patterns

    value = "CC(=O)N2" + "as" + "pian"
    assert remaining_patterns(_drug_table("canonical_smiles", value), _allow()) == ["atlas"]


def test_a_ragged_table_is_scanned_as_written():
    """Rows that do not match the columns are not mapped, so no exemption applies."""
    from scripts.eval_pack import remaining_patterns

    table = {"columns": ["drug", "canonical_smiles"], "rows": [[_TRAMETINIB_SMILES]]}
    assert remaining_patterns(table, _allow()) == ["internal_ref"]


@pytest.mark.parametrize(
    "entry",
    [
        {"key": "canonical_smiles", "pattern": "internal_ref"},
        {"key": "canonical_smiles", "pattern": "internal_ref", "shape": "smiles", "value": "C"},
        {"key": "canonical_smiles", "pattern": "internal_ref", "shape": "inchi"},
    ],
)
def test_an_allowlist_entry_needs_exactly_one_known_value_or_shape(tmp_path, entry):
    from scripts.eval_pack import load_disclosure_allowlist

    target = tmp_path / "evals" / "disclosure_allow.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"allow": [entry]}), encoding="utf-8")
    with pytest.raises(EvalError, match="malformed"):
        load_disclosure_allowlist(tmp_path)


# --- route grader on the trace ------------------------------------------------

_INIT_LINE = (
    '{"type":"system","subtype":"init","tools":["Read",'
    '"mcp__plugin_tara_tahoe-public__get_expression_slice",'
    '"mcp__plugin_tara_tahoe-public__get_differential_expression"]}'
)
_CALL_LINE = (
    '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t1",'
    '"name":"mcp__plugin_tara_tahoe-public__get_expression_slice","input":{}}]}}'
)
_OTHER_CALL = (
    '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t2",'
    '"name":"mcp__plugin_tara_tahoe-public__get_pathway_scores","input":{}}]}}'
)


def _route_grader(suite: Path, case: str) -> dict:
    from scripts.eval_pack import parse_frontmatter

    fields, _ = parse_frontmatter((suite / case / "graders" / "route.md").read_text())
    return fields


@pytest.mark.parametrize("case", ["e1-trametinib-expression", "s6-expression-control"])
def test_route_grader_reads_real_calls_in_the_trace(suite, case):
    """No mock calls exist when the proxy serves the tools. The route grader reads the
    trace and matches a tool call, never the tool listing on the init line."""
    fields = _route_grader(suite, case)
    assert fields["target"] == "trace"
    pattern = re.compile(str(fields["pattern"]))
    assert pattern.search(_CALL_LINE)
    assert not pattern.search(_INIT_LINE)
    assert not pattern.search(_INIT_LINE + "\n" + _OTHER_CALL)
