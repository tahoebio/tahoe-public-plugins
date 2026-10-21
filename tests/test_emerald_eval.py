"""Exercise evidence-completeness failure paths with synthetic in-memory records.

No test record here is a scientific result or evidence of a real host execution.
"""

from __future__ import annotations

import copy
import hashlib
import json

import pytest
from jsonschema import Draft202012Validator

from evals.tara import check_emerald as checker
from scripts import common

EVAL_ROOT = common.REPO_ROOT / "evals" / "tara"
PACK = common.load_json(EVAL_ROOT / "emerald-cases.json")
SCHEMA = common.load_json(EVAL_ROOT / "emerald-record.schema.json")
TEMPLATE = common.load_json(EVAL_ROOT / "emerald-run-record.template.json")


def artifact(label):
    return {"ref": f"synthetic-tests/{label}.json", "sha256": "a" * 64}


def synthetic_record():
    """Complete fictional attestations to test logic, never persisted as results."""
    record = copy.deepcopy(TEMPLATE)
    record.update(
        status="reviewed",
        plugin_commit="b" * 40,
        pack_sha256=hashlib.sha256(
            json.dumps(PACK, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    )
    record["oracle"].update(
        source_revision="c" * 40,
        reviewer="synthetic unit test",
        reviewed_at="2026-01-01T00:00:00Z",
        reviewed_before_candidate_results=True,
        snapshot=artifact("source"),
        derivation=artifact("derivation"),
    )
    record["runs"] = []
    for case in PACK["cases"]:
        for host in PACK["hosts"]:
            run = {
                "case_id": case["id"],
                "host": host,
                "status": "pass",
                "evidence_kind": case["evidence_kind"],
                "fresh_session": True,
                "session_label": f"synthetic-{case['id']}-{host}",
                "host_version": "unit-test-only",
                "model": "unit-test-only",
                "started_at": "2026-01-02T00:00:00Z",
                "reviewer": "synthetic unit test",
                "plugin_commit": record["plugin_commit"],
                "server_version": "0.4.0",
                "server_state": case["server_state"],
                "transcript": artifact("transcript"),
                "tool_trace": artifact("trace"),
                "comparison": artifact("comparison"),
                "criteria": [
                    {
                        "id": criterion["id"],
                        "status": "pass",
                        "evidence": "synthetic unit test only",
                    }
                    for criterion in case["hard_criteria"]
                ],
            }
            if case["evidence_kind"] == "real-remote-session":
                run.update(
                    endpoint=common.MCP_ENDPOINT,
                    release="emerald-bay/v1",
                    guide_version="d" * 64,
                )
            else:
                run["capability_fixture"] = artifact("capabilities")
            if case.get("additional_approval"):
                run["approval_reference"] = "synthetic-approval-test-only"
            record["runs"].append(run)
    return record


def test_pack_and_template_structure_do_not_claim_live_readiness():
    checker.validate_pack(PACK)
    Draft202012Validator.check_schema(SCHEMA)
    Draft202012Validator(SCHEMA).validate(TEMPLATE)
    report = checker.assess(TEMPLATE, PACK)
    assert report["ready"] is False
    assert report["required_runs"] == 46


def test_complete_synthetic_attestation_checks_only_evidence_completeness():
    record = synthetic_record()
    Draft202012Validator(SCHEMA).validate(record)
    report = checker.assess(record, PACK)
    assert report["ready"] is True
    assert report["required_runs"] == report["recorded_runs"] == 46
    assert report["evidence_counts"] == {
        "real-remote-session": 42,
        "offline-contract": 4,
    }
    assert "Evidence completeness only" in report["note"]


@pytest.mark.parametrize("status", ["fail", "blocked", "not_run"])
def test_any_nonpassing_case_or_criterion_blocks_release(status):
    record = synthetic_record()
    record["runs"][0]["status"] = status
    assert checker.assess(record, PACK)["ready"] is False
    record["runs"][0]["status"] = "pass"
    record["runs"][0]["criteria"][0]["status"] = status
    assert checker.assess(record, PACK)["ready"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_run",
        "duplicate_run",
        "missing_host",
        "missing_criterion",
        "duplicate_criterion",
        "unknown_criterion",
        "missing_evidence",
        "offline_for_live",
        "changed_commit",
        "missing_hash",
        "reused_session",
        "not_fresh",
        "wrong_state",
        "missing_approval",
    ],
)
def test_no_missing_duplicate_or_substituted_evidence_can_pass(mutation):
    record = synthetic_record()
    run = record["runs"][0]
    if mutation == "missing_run":
        record["runs"].pop()
    elif mutation == "duplicate_run":
        record["runs"].append(copy.deepcopy(run))
    elif mutation == "missing_host":
        record["runs"] = [item for item in record["runs"] if item["host"] == "Codex"]
    elif mutation == "missing_criterion":
        run["criteria"].pop()
    elif mutation == "duplicate_criterion":
        run["criteria"].append(copy.deepcopy(run["criteria"][0]))
    elif mutation == "unknown_criterion":
        run["criteria"][0]["id"] = "EB99.1"
    elif mutation == "missing_evidence":
        run["criteria"][0]["evidence"] = ""
    elif mutation == "offline_for_live":
        run["evidence_kind"] = "offline-contract"
    elif mutation == "changed_commit":
        run["plugin_commit"] = "f" * 40
    elif mutation == "missing_hash":
        del run["transcript"]["sha256"]
    elif mutation == "reused_session":
        record["runs"][1]["session_label"] = run["session_label"]
    elif mutation == "not_fresh":
        run["fresh_session"] = False
    elif mutation == "wrong_state":
        run["server_state"] = "different-state"
    elif mutation == "missing_approval":
        approved = next(item for item in record["runs"] if "approval_reference" in item)
        del approved["approval_reference"]
    assert checker.assess(record, PACK)["ready"] is False, mutation


@pytest.mark.parametrize(
    "mutation",
    [
        "not_reviewed",
        "missing_status",
        "unknown_property",
        "wrong_origin",
        "mutable_source",
        "oracle_after_candidate",
        "unreviewed_oracle",
        "invalid_oracle_date",
        "invalid_run_date",
        "missing_timezone",
        "invalid_server",
        "old_server",
        "wrong_pack_hash",
        "secret_field",
        "raw_handle",
    ],
)
def test_bad_metadata_does_not_turn_attestations_into_readiness(mutation):
    record = synthetic_record()
    run = next(
        item for item in record["runs"] if item["server_state"] == "emerald-available"
    )
    if mutation == "not_reviewed":
        record["status"] = "in_progress"
    elif mutation == "missing_status":
        del record["status"]
    elif mutation == "unknown_property":
        record["ready"] = True
    elif mutation == "wrong_origin":
        record["oracle"]["expected_values_origin"] = "candidate-tool-results"
    elif mutation == "mutable_source":
        record["oracle"]["source_revision"] = "main"
    elif mutation == "oracle_after_candidate":
        record["oracle"]["reviewed_at"] = "2026-02-01T00:00:00Z"
    elif mutation == "unreviewed_oracle":
        record["oracle"]["reviewed_before_candidate_results"] = False
    elif mutation == "invalid_oracle_date":
        record["oracle"]["reviewed_at"] = "not-a-date"
    elif mutation == "invalid_run_date":
        run["started_at"] = "not-a-date"
    elif mutation == "missing_timezone":
        run["started_at"] = "2026-01-02T00:00:00"
    elif mutation == "invalid_server":
        run["server_version"] = "unknown"
    elif mutation == "old_server":
        run["server_version"] = "0.3.9"
    elif mutation == "wrong_pack_hash":
        record["pack_sha256"] = "f" * 64
    elif mutation == "secret_field":
        run["authorization"] = "synthetic-unit-test-only"
    elif mutation == "raw_handle":
        run["result_handle"] = "synthetic-unit-test-only"
    assert checker.assess(record, PACK)["ready"] is False, mutation


def test_old_server_refusal_case_can_record_old_version():
    record = synthetic_record()
    for run in record["runs"]:
        if run["case_id"] == "EB15":
            run["server_version"] = "0.3.9"
    assert checker.assess(record, PACK)["ready"] is True


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_case",
        "duplicate_case",
        "renamed_case",
        "missing_criterion",
        "duplicate_criterion",
        "wrong_fixture",
        "unknown_tool",
        "downgraded_evidence",
        "wrong_state",
        "missing_approval_gate",
    ],
)
def test_pack_cannot_omit_required_coverage(mutation):
    pack = copy.deepcopy(PACK)
    if mutation == "missing_case":
        pack["cases"].pop()
    elif mutation == "duplicate_case":
        pack["cases"].append(copy.deepcopy(pack["cases"][0]))
    elif mutation == "renamed_case":
        pack["cases"][-1]["id"] = "EB99"
    elif mutation == "missing_criterion":
        pack["cases"][0]["hard_criteria"] = []
    elif mutation == "duplicate_criterion":
        pack["cases"][0]["hard_criteria"].append(
            copy.deepcopy(pack["cases"][0]["hard_criteria"][0])
        )
    elif mutation == "wrong_fixture":
        pack["cases"][0]["fixtures"] = ["undeclared"]
    elif mutation == "unknown_tool":
        pack["cases"][0]["expected_tools"] = ["invented_tool"]
    elif mutation == "downgraded_evidence":
        pack["cases"][0]["evidence_kind"] = "offline-contract"
    elif mutation == "wrong_state":
        pack["cases"][0]["server_state"] = "old-server"
    elif mutation == "missing_approval_gate":
        pack["cases"][-1]["additional_approval"] = None
    with pytest.raises(ValueError):
        checker.validate_pack(pack)


def test_cli_empty_template_fails_and_pack_check_has_no_live_pass(capsys):
    assert checker.main(["--pack", str(EVAL_ROOT / "emerald-cases.json")]) == 0
    assert json.loads(capsys.readouterr().out)["live_verification"] == "not_performed"
    assert (
        checker.main(
            [
                "--pack",
                str(EVAL_ROOT / "emerald-cases.json"),
                "--record",
                str(EVAL_ROOT / "emerald-run-record.template.json"),
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["ready"] is False
