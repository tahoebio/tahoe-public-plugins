"""Offline Emerald eval-pack and evidence-record checks. Never calls any service.

A ready record is a complete set of reviewer attestations with evidence references;
this checker cannot establish that an external transcript or scientific result is
true. Review the referenced evidence independently before approving a release.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator

PACK_PATH = Path(__file__).with_name("emerald-cases.json")
SCHEMA_PATH = Path(__file__).with_name("emerald-record.schema.json")
HOSTS = {"Codex", "Claude Code"}
KINDS = {"offline-contract", "real-remote-session"}
STATUSES = {"pass", "fail", "blocked", "not_run"}
CASE_IDS = {f"EB{number:02d}" for number in range(1, 24)}
OFFLINE_CASE_IDS = {"EB15", "EB17"}
TOOLS = {
    "health",
    "list_releases",
    "get_guide",
    "search_conditions",
    "resolve_genes",
    "list_cell_lines",
    "get_drug_info",
    "get_expression_slice",
    "get_phenotype_scores",
    "search_gene_sets",
    "get_pathway_scores",
    "run_sql",
    "get_differential_expression",
    "get_embedding_distance",
    "get_perturbation_markers",
    "cancel_execution",
    "send_feedback",
}
SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
SECRET_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "result_handle",
    "cancel_handle",
}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def validate_pack(pack: dict) -> None:
    """Validate declared coverage; this is structural validation, never a live pass."""
    _need(
        isinstance(pack, dict) and pack.get("format_version") == 1, "wrong pack format"
    )
    _need(pack.get("dataset") == "emerald-bay", "wrong dataset")
    _need(pack.get("release") == "emerald-bay/v1", "wrong release")
    _need(pack.get("feature_server_version") == "0.4.0", "wrong feature version")
    _need(set(pack.get("hosts", [])) == HOSTS, "both supported hosts are required")
    _need(set(pack.get("tools", [])) == TOOLS, "tool coverage must name all 17 tools")
    cases = pack.get("cases")
    _need(isinstance(cases, list) and cases, "missing cases")
    seen, criteria, covered = set(), set(), set()
    for case in cases:
        case_id = case.get("id")
        _need(
            isinstance(case_id, str) and re.fullmatch(r"EB[0-9]{2}", case_id),
            "bad case id",
        )
        _need(case_id not in seen, "duplicate case id")
        seen.add(case_id)
        _need(case.get("evidence_kind") in KINDS, f"{case_id}: invalid evidence kind")
        expected_kind = (
            "offline-contract" if case_id in OFFLINE_CASE_IDS else "real-remote-session"
        )
        _need(
            case.get("evidence_kind") == expected_kind,
            f"{case_id}: evidence kind differs from the release gate",
        )
        expected_state = {
            "EB15": "older-tahoe-only",
            "EB16": "emerald-not-visible",
            "EB17": "incomplete-capability-fixtures",
        }.get(case_id, "emerald-available")
        _need(
            case.get("server_state") == expected_state,
            f"{case_id}: server state differs from the release gate",
        )
        if case_id == "EB23":
            _need(
                case.get("additional_approval") == "synthetic-feedback-submission",
                "EB23: synthetic feedback requires separate approval",
            )
        _need(
            bool(case.get("prompt")) and bool(case.get("server_state")),
            f"{case_id}: missing prompt/state",
        )
        fields = set(re.findall(r"\{([a-z_]+)\}", case["prompt"]))
        _need(
            fields == set(case.get("fixtures", [])),
            f"{case_id}: fixture placeholders disagree",
        )
        tools = case.get("expected_tools", [])
        _need(bool(tools) and set(tools) <= TOOLS, f"{case_id}: unknown/missing tools")
        covered.update(tools)
        checks = case.get("hard_criteria")
        _need(isinstance(checks, list) and checks, f"{case_id}: missing hard criteria")
        for check in checks:
            key = check.get("id")
            _need(
                isinstance(key, str)
                and re.fullmatch(re.escape(case_id) + r"\.[1-9][0-9]*", key),
                "bad criterion id",
            )
            _need(
                key not in criteria and bool(check.get("assertion")),
                "duplicate/empty criterion",
            )
            criteria.add(key)
    _need(seen == CASE_IDS, "release gate requires exactly EB01 through EB23")
    _need(
        covered | set(pack.get("unsupported_emerald_tools", [])) == TOOLS,
        "tool routing coverage incomplete",
    )


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _hash(value, pattern):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",
        value,
    ):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", value
    ):
        return None
    return tuple(int(part) for part in value.split("."))


def _artifact(value):
    if not isinstance(value, dict):
        return False
    ref = value.get("ref")
    return (
        _nonempty(ref)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", ref) is not None
        and ".." not in ref.split("/")
        and _hash(value.get("sha256"), SHA256)
    )


def _has_secret_fields(value):
    if isinstance(value, dict):
        return any(
            k.lower() in SECRET_KEYS or _has_secret_fields(v) for k, v in value.items()
        )
    if isinstance(value, list):
        return any(_has_secret_fields(v) for v in value)
    return False


def assess(record: dict, pack: dict) -> dict:
    """Recompute completeness from every case/host/criterion; ignore saved verdicts."""
    validate_pack(pack)
    problems = []
    validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))
    structural_errors = list(validator.iter_errors(record))
    if structural_errors:
        return {
            "ready": False,
            "problems": [
                f"record schema: {'/'.join(map(str, error.absolute_path)) or '/'}: {error.validator}"
                for error in structural_errors
            ],
            "required_runs": len(pack["cases"]) * 2,
        }
    if record.get("status") != "reviewed":
        problems.append("record status must be reviewed")
    if record.get("format_version") != 1 or record.get("dataset") != "emerald-bay":
        problems.append("wrong record format/dataset")
    if _has_secret_fields(record):
        problems.append("record contains forbidden secret or handle fields")
    if not _hash(record.get("plugin_commit"), COMMIT):
        problems.append("exact plugin commit is required")
    if not _hash(record.get("pack_sha256"), SHA256):
        problems.append("pack SHA256 is required")
    else:
        import hashlib

        actual = hashlib.sha256(
            json.dumps(pack, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if record["pack_sha256"] != actual:
            problems.append("pack SHA256 mismatch")
    oracle = record.get("oracle", {})
    if not isinstance(oracle, dict):
        oracle = {}
    if oracle.get("expected_values_origin") != "independent-released-source":
        problems.append("expected values must come from independent released source")
    if oracle.get("reviewed_before_candidate_results") is not True:
        problems.append("oracle must be reviewed before candidate results")
    for field in ("source_revision", "reviewer", "reviewed_at"):
        if not _nonempty(oracle.get(field)):
            problems.append(f"oracle {field} is required")
    if not _hash(oracle.get("source_revision"), COMMIT):
        problems.append(
            "oracle source revision must be an immutable 40-character commit"
        )
    reviewed_at = _timestamp(oracle.get("reviewed_at"))
    if reviewed_at is None:
        problems.append("oracle reviewed_at must be an ISO timestamp with timezone")
    if (
        oracle.get("source_url")
        != "https://huggingface.co/datasets/tahoebio/EmeraldBay"
    ):
        problems.append("public Emerald source reference is required")
    for field in ("snapshot", "derivation"):
        if not _artifact(oracle.get(field)):
            problems.append(f"oracle {field} evidence is required")
    if oracle.get("calculated_tolerance") != {"rtol": 1e-9, "atol": 1e-12}:
        problems.append("calculated tolerance differs from reviewed contract")
    cases = {case["id"]: case for case in pack["cases"]}
    expected = {(case_id, host) for case_id in cases for host in HOSTS}
    seen, sessions = set(), set()
    counts = {kind: 0 for kind in KINDS}
    runs = record.get("runs", [])
    if not isinstance(runs, list):
        runs = []
        problems.append("runs must be an array")
    for run in runs:
        if not isinstance(run, dict):
            problems.append("run must be an object")
            continue
        key = (run.get("case_id"), run.get("host"))
        label = f"{key[0]}/{key[1]}"
        if key not in expected:
            problems.append(f"{label}: unknown case/host")
            continue
        if key in seen:
            problems.append(f"{label}: duplicate run")
        seen.add(key)
        case = cases[key[0]]
        if run.get("evidence_kind") != case["evidence_kind"]:
            problems.append(
                f"{label}: wrong evidence kind; offline results cannot prove a remote case"
            )
        if run.get("status") != "pass":
            problems.append(f"{label}: case is not passed")
        if run.get("fresh_session") is not True:
            problems.append(f"{label}: fresh session is required")
        session = run.get("session_label")
        if not _nonempty(session) or session in sessions:
            problems.append(f"{label}: missing/reused session label")
        else:
            sessions.add(session)
        for field in (
            "host_version",
            "model",
            "started_at",
            "reviewer",
            "server_version",
        ):
            if not _nonempty(run.get(field)):
                problems.append(f"{label}: {field} is required")
        started_at = _timestamp(run.get("started_at"))
        if started_at is None:
            problems.append(
                f"{label}: started_at must be an ISO timestamp with timezone"
            )
        elif reviewed_at is not None and started_at < reviewed_at:
            problems.append(f"{label}: oracle review must precede candidate execution")
        server_version = _version(run.get("server_version"))
        if server_version is None:
            problems.append(
                f"{label}: server_version must be a numeric semantic version"
            )
        elif case["server_state"] == "emerald-available" and server_version < (0, 4, 0):
            problems.append(f"{label}: Emerald requires server_version >= 0.4.0")
        if run.get("plugin_commit") != record.get("plugin_commit"):
            problems.append(f"{label}: plugin revision mismatch")
        if run.get("server_state") != case["server_state"]:
            problems.append(f"{label}: wrong server-state evidence")
        for field in ("transcript", "tool_trace", "comparison"):
            if not _artifact(run.get(field)):
                problems.append(f"{label}: {field} artifact/hash is required")
        if case["evidence_kind"] == "real-remote-session":
            counts["real-remote-session"] += 1
            if run.get("endpoint") != "https://tara.tahoebio.io/mcp":
                problems.append(f"{label}: wrong or missing public endpoint")
            if case["server_state"] == "emerald-available" and (
                run.get("release") != "emerald-bay/v1"
                or not _hash(run.get("guide_version"), SHA256)
            ):
                problems.append(f"{label}: release/guide version is required")
        else:
            counts["offline-contract"] += 1
            if not _artifact(run.get("capability_fixture")):
                problems.append(f"{label}: capability fixture/hash is required")
        if case.get("additional_approval") and not _nonempty(
            run.get("approval_reference")
        ):
            problems.append(f"{label}: explicit additional approval is required")
        checks = run.get("criteria", [])
        expected_checks = {c["id"] for c in case["hard_criteria"]}
        if not isinstance(checks, list):
            checks = []
        actual_checks = []
        for check in checks:
            if not isinstance(check, dict):
                problems.append(f"{label}: invalid criterion record")
                continue
            actual_checks.append(check.get("id"))
            if check.get("status") != "pass" or not _nonempty(check.get("evidence")):
                problems.append(
                    f"{label}: criterion {check.get('id')} not passed with evidence"
                )
        if set(actual_checks) != expected_checks or len(actual_checks) != len(
            expected_checks
        ):
            problems.append(f"{label}: missing, duplicate or unknown criteria")
    problems.extend(
        f"{case}/{host}: missing run" for case, host in sorted(expected - seen)
    )
    return {
        "ready": not problems,
        "required_runs": len(expected),
        "recorded_runs": len(runs),
        "evidence_counts": counts,
        "problems": problems,
        "note": "Evidence completeness only; review the independent oracle, transcripts and comparisons. No approval or live execution is performed by this checker.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=PACK_PATH)
    parser.add_argument("--record", type=Path)
    args = parser.parse_args(argv)
    try:
        pack = json.loads(args.pack.read_text())
        validate_pack(pack)
        if args.record is None:
            print(
                json.dumps(
                    {
                        "pack_valid": True,
                        "cases": len(pack["cases"]),
                        "live_verification": "not_performed",
                    }
                )
            )
            return 0
        report = assess(json.loads(args.record.read_text()), pack)
        print(json.dumps(report, indent=2))
        return 0 if report["ready"] else 1
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"ready": False, "error": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
