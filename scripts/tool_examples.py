"""Offline contracts and worked-call validation; no client or warehouse execution.

The fixtures describe routing requirements for the skill. They do not simulate
an agent following prose and are not evidence of a successful host session.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import common  # noqa: E402

CONTRACT_REL = "tests/fixtures/public_tool_contract.json"
EXAMPLES_REL = "tests/fixtures/tool_examples.json"
#: The server version the public tool snapshot was exported from.
CONTRACT_SERVER_VERSION = "0.5.0"
EMERALD = "emerald-bay"
TAHOE = "tahoe-100m"
EMERALD_MINIMUM = (0, 4, 0)
#: The validated-signatures panel: its lookup tool, the argument that resolves a
#: process to its readout, and its guide topic. They exist from server 0.5.0 and
#: work only while discovery shows the panel; the server's default is disabled.
SIGNATURES_MINIMUM = (0, 5, 0)
SIGNATURE_TOOLS = frozenset({"get_validated_signatures"})
SIGNATURE_ARGUMENTS = {"get_pathway_scores": frozenset({"process"})}
EMERALD_ARGUMENTS = {
    "search_conditions": {"samples"},
    "get_drug_info": {"samples"},
    "get_expression_slice": {"samples", "cell_lines", "limit"},
    "get_phenotype_scores": {"samples"},
    "get_pathway_scores": {"samples", "score_kind"},
}
DISCOVERY_LISTS = (
    "tools",
    "tables",
    "expression_measurements",
    "phenotype_measurements",
    "pathway_score_kinds",
)
FENCES = re.compile(r"^```json[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
GLOBAL_TOOLS = frozenset(
    {"health", "list_releases", "cancel_execution", "send_feedback"}
)


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+\.\d+", value):
        return None
    return tuple(int(part) for part in value.split("."))


def schema_problems(contract, request):
    if not isinstance(request, dict):
        return ["a worked call must be an object"]
    if (
        set(request) - {"id", "tool", "arguments"}
        or not {"tool", "arguments"} <= request.keys()
    ):
        return [
            "a worked call must contain tool and arguments only, with an optional id"
        ]
    if not isinstance(request["tool"], str) or request["tool"] not in contract["tools"]:
        return ["unknown tool"]
    schema = contract["tools"][request["tool"]]
    arguments = request["arguments"]
    if not isinstance(arguments, dict):
        return ["arguments must be an object"]
    errors = []
    if set(arguments) - schema.get("properties", {}).keys():
        errors.append("undeclared argument")
    errors.extend(
        error.message for error in Draft202012Validator(schema).iter_errors(arguments)
    )
    return errors


def sql_example_allowed(statement, tables, max_rows=200):
    """Narrow documentation-example checks; the server remains the SQL authority."""
    if type(max_rows) is not int or not 1 <= max_rows <= 1000:
        return False
    if not isinstance(statement, str) or not re.match(
        r"^\s*SELECT\b", statement, re.IGNORECASE
    ):
        return False
    if ";" in statement or common.locator_tokens(statement):
        return False
    # Examples deliberately use simple unqualified table aliases. This is not a
    # general SQL parser or a replacement for the server's semantic SQL policy.
    without_literals = re.sub(r"'(?:''|[^'])*'", "''", statement)
    refs = re.findall(
        r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w.]*)", without_literals, re.IGNORECASE
    )
    if not refs or any(ref not in tables for ref in refs):
        return False
    limit = re.search(r"\bLIMIT\s+(\d+)\s*$", statement, re.IGNORECASE)
    return limit is None or 1 <= int(limit.group(1)) <= 1000


def uses_signatures(contract, request):
    """True when a call needs the validated-signatures panel to be visible."""
    tool = request.get("tool") if isinstance(request, dict) else None
    args = request.get("arguments") if isinstance(request, dict) else None
    if not isinstance(args, dict):
        args = {}
    if tool in SIGNATURE_TOOLS:
        return True
    if tool == "get_guide" and args.get("topic") in contract["signatures"]["guide_topics"]:
        return True
    return any(args.get(field) is not None for field in SIGNATURE_ARGUMENTS.get(tool, ()))


def signatures_problem(contract, context, version):
    """Why the panel cannot serve this caller, or None.

    Like Emerald, a version alone never authorizes it: complete discovery must
    show the panel (`list_releases` nests it on the Tahoe-100M entry) at the
    snapshot's release.
    """
    if version is None:
        return "compatibility_unknown"
    if version < SIGNATURES_MINIMUM:
        return "server_too_old"
    if (
        context.get("discovery_ok") is not True
        or context.get("discovery_truncated") is not False
    ):
        return "discovery_incomplete"
    discovered = context.get("advertised_signatures")
    if (
        not isinstance(discovered, dict)
        or discovered.get("release") != contract["signatures"]["release"]
    ):
        return "signatures_unavailable"
    return None


def route(contract, context, request):
    if schema_problems(contract, request):
        return "invalid_arguments"
    tool, args = request["tool"], request["arguments"]
    if tool in GLOBAL_TOOLS:
        return "send"
    dataset = args.get("dataset") or TAHOE
    if dataset not in contract["datasets"]:
        return "dataset_unavailable"
    version = version_tuple(context.get("server_version"))
    panel = uses_signatures(contract, request)
    if panel:
        problem = signatures_problem(contract, context, version)
        if problem is not None:
            return problem
    if dataset == TAHOE:
        introduced = EMERALD_ARGUMENTS.get(tool, set()) | {"dataset"}
        if (
            version is not None
            and version < EMERALD_MINIMUM
            and introduced & args.keys()
        ):
            return "unsupported_argument"
        if any(
            args.get(field) is not None for field in EMERALD_ARGUMENTS.get(tool, ())
        ):
            return "unsupported_argument"
    if dataset == EMERALD:
        if version is None:
            return "compatibility_unknown"
        if version < EMERALD_MINIMUM:
            return "server_too_old"
    advertised = context.get("advertised_datasets")
    if not isinstance(advertised, list) or dataset not in advertised:
        return "dataset_unavailable"
    capabilities = contract["datasets"][dataset]
    if dataset == EMERALD:
        # Context is a normalized discovery fixture, not a claimed MCP response.
        # Require successful complete discovery and the selected release's actual
        # capability fields. The pinned schema alone cannot establish visibility.
        if (
            context.get("discovery_ok") is not True
            or context.get("discovery_truncated") is not False
        ):
            return "discovery_incomplete"
        discovered = context.get("advertised_capabilities", {}).get(dataset)
        if (
            not isinstance(discovered, dict)
            or discovered.get("release") != capabilities["release"]
        ):
            return "discovery_incomplete"
        for key in DISCOVERY_LISTS:
            values = discovered.get(key)
            if not isinstance(values, list) or not all(
                isinstance(value, str) for value in values
            ):
                return "discovery_incomplete"
        # Only capabilities present in BOTH the reviewed contract and discovery
        # can authorize a documentation example in this offline requirements model.
        capabilities = dict(capabilities)
        for key in DISCOVERY_LISTS:
            capabilities[key] = [
                value for value in capabilities[key] if value in discovered[key]
            ]
    if tool not in capabilities["tools"]:
        return "unsupported_tool"
    if dataset == EMERALD:
        unsupported_filters = {
            "search_conditions": ("dose",),
            "list_cell_lines": ("organ",),
            "get_drug_info": ("moa", "target"),
            "get_phenotype_scores": ("dose",),
            "get_pathway_scores": ("dose",),
        }
        if any(
            args.get(field) is not None for field in unsupported_filters.get(tool, ())
        ):
            return "unsupported_filter"
    if tool == "get_guide" and args.get("topic") is not None:
        # The panel's topic is served beside either dataset's guide once visible.
        if args["topic"] not in capabilities["guide_topics"] and not panel:
            return "unsupported_topic"
    if tool == "get_expression_slice":
        measurement = args.get("measurement") or "cpm_log1p"
        if measurement not in capabilities["expression_measurements"]:
            return "unsupported_measurement"
    if tool == "get_phenotype_scores" and dataset == EMERALD:
        phenotypes = args.get("phenotypes") or ["growth_rate_released"]
        if isinstance(phenotypes, str):
            phenotypes = [phenotypes]
        if any(
            ("growth_rate_released" if name == "survival" else name)
            not in capabilities["phenotype_measurements"]
            for name in phenotypes
        ):
            return "unsupported_measurement"
        if args.get("significant_only"):
            return "unsupported_measurement"
    if tool == "get_pathway_scores" and dataset == EMERALD:
        if (args.get("score_kind") or "differential") not in capabilities[
            "pathway_score_kinds"
        ]:
            return "unsupported_score_kind"
    if tool == "run_sql" and not sql_example_allowed(
        args.get("statement"),
        capabilities["tables"],
        (200 if args.get("max_rows") is None else args["max_rows"]),
    ):
        return "sql_not_allowed"
    return "send"


def fenced_calls(text, label="text"):
    calls = []
    for index, match in enumerate(FENCES.finditer(text), 1):
        try:
            parsed = json.loads(match.group(1))
        except ValueError as exc:
            raise common.RepoError(f"{label}: invalid JSON fence {index}") from exc
        if isinstance(parsed, dict) and "tool" in parsed:
            calls.append(parsed)
        elif isinstance(parsed, list) and any(
            isinstance(item, dict) and "tool" in item for item in parsed
        ):
            if not all(isinstance(item, dict) and "tool" in item for item in parsed):
                raise common.RepoError(f"{label}: mixed tool-call JSON array")
            calls.extend(parsed)
    return calls


def legacy_calls(text, label="text"):
    """Parse existing literal-only text examples with AST; never execute them."""
    calls = []

    def value(node):
        if isinstance(node, ast.Name) and node.id in {"true", "false", "null"}:
            return {"true": True, "false": False, "null": None}[node.id]
        if isinstance(node, ast.List):
            return [value(item) for item in node.elts]
        if isinstance(node, ast.Dict):
            return {value(k): value(v) for k, v in zip(node.keys, node.values)}
        return ast.literal_eval(node)

    for match in re.finditer(
        r"^```text[ \t]*\n(.*?)^```[ \t]*$", text, re.MULTILINE | re.DOTALL
    ):
        block = match.group(1)
        if not any(
            re.search(rf"^\s*{re.escape(tool)}\(", block, re.MULTILINE)
            for tool in common.PINNED_PUBLIC_TOOLS
        ):
            continue
        try:
            nodes = ast.parse(block).body
            for node in nodes:
                if not isinstance(node, ast.Expr) or not isinstance(
                    node.value, ast.Call
                ):
                    raise ValueError("not a tool call")
                call = node.value
                if (
                    not isinstance(call.func, ast.Name)
                    or call.args
                    or any(k.arg is None for k in call.keywords)
                ):
                    raise ValueError("only named literal arguments are supported")
                calls.append(
                    {
                        "tool": call.func.id,
                        "arguments": {k.arg: value(k.value) for k in call.keywords},
                    }
                )
        except (ValueError, SyntaxError) as exc:
            raise common.RepoError(
                f"{label}: legacy worked calls must use literal named arguments"
            ) from exc
    return calls


def validate_fixtures(root=ROOT):
    contract = common.load_json(root / CONTRACT_REL)
    fixtures = common.load_json(root / EXAMPLES_REL)
    if (
        contract.get("server_version") != CONTRACT_SERVER_VERSION
        or set(contract["tools"]) != common.PINNED_PUBLIC_TOOLS
    ):
        raise common.RepoError("public tool snapshot version or tool surface changed")
    panel = contract.get("signatures")
    if (
        not isinstance(panel, dict)
        or not isinstance(panel.get("release"), str)
        or not isinstance(panel.get("guide_topics"), list)
        or not SIGNATURE_TOOLS <= set(panel.get("tools", ()))
    ):
        raise common.RepoError("public tool snapshot lacks the validated-signatures panel")
    for schema in contract["tools"].values():
        Draft202012Validator.check_schema(schema)
    seen, covered = set(), set()
    for case in fixtures["cases"]:
        if case["id"] in seen:
            raise common.RepoError("duplicate worked example id")
        seen.add(case["id"])
        request = {key: case[key] for key in ("tool", "arguments")}
        outcome = route(contract, fixtures["contexts"][case["context"]], request)
        if outcome != case["expected_route"]:
            raise common.RepoError(
                f"example {case['id']}: expected {case['expected_route']}, got {outcome}"
            )
        if outcome == "send":
            covered.add(case["tool"])
    if covered != common.PINNED_PUBLIC_TOOLS:
        raise common.RepoError("worked fixtures must cover every registered tool")
    for rel in (CONTRACT_REL, EXAMPLES_REL):
        findings = common.scan_text((root / rel).read_text())
        if findings or common.locator_tokens(json.dumps(common.load_json(root / rel))):
            raise common.RepoError(f"{rel}: unsafe public fixture content")
    return contract, fixtures


def validate_shipped_calls(root=ROOT, *, require_emerald=True):
    contract, fixtures = validate_fixtures(root)
    calls = []
    for rel in common.SKILL_FILES:
        text = (root / rel).read_text()
        in_emerald_section = False
        section_lines = []
        for line in text.splitlines(keepends=True):
            if line.startswith("## "):
                in_emerald_section = line.strip() == "## Emerald Bay worked calls"
            if in_emerald_section:
                section_lines.append(line)
        for request in fenced_calls("".join(section_lines), rel):
            if request.get("arguments", {}).get("dataset") != EMERALD:
                raise common.RepoError(
                    f"{rel}: every Emerald worked call must select its dataset explicitly"
                )
        for request in [*fenced_calls(text, rel), *legacy_calls(text, rel)]:
            if uses_signatures(contract, request):
                name = "signatures_visible"
            elif request.get("arguments", {}).get("dataset") == EMERALD:
                name = "emerald_visible"
            else:
                name = "tahoe_legacy"
            context = fixtures["contexts"][name]
            outcome = route(contract, context, request)
            if outcome != "send":
                raise common.RepoError(
                    f"{rel}: worked call {request.get('tool')} is {outcome}"
                )
            calls.append(request)
    if require_emerald:
        emerald = [
            call for call in calls if call["arguments"].get("dataset") == EMERALD
        ]
        required = set(contract["datasets"][EMERALD]["tools"])
        if not required <= {call["tool"] for call in emerald}:
            raise common.RepoError(
                "shipped JSON worked calls must cover every supported Emerald tool"
            )
        measurements = {
            call["arguments"].get("measurement")
            for call in emerald
            if call["tool"] == "get_expression_slice"
        }
        if not {"raw_counts", "cpm", "cpm_log1p"} <= measurements:
            raise common.RepoError(
                "shipped expression examples must cover raw counts, CPM and log1p(CPM)"
            )
        if not any(
            call["tool"] == "get_expression_slice"
            and "dataset" not in call["arguments"]
            for call in calls
        ):
            raise common.RepoError(
                "preserve a worked Tahoe expression call without a dataset argument"
            )
    return calls


# Executed only with an explicitly supplied local candidate path/interpreter.
# The process has no credentials, no network use and does not call data tools.
EXPORT_PROGRAM = r"""
import asyncio, json, sys, tempfile
from pathlib import Path
from fastmcp import FastMCP
from server import datasets, registry_view, signatures, skills, tools
from server.config import Config
from server.version import server_version

def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if k not in ("description", "title")}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value

async def export():
    with tempfile.TemporaryDirectory() as directory:
        config = Config(github_client_id="offline", github_client_secret="offline",
            jwt_signing_key="x"*48, base_url="https://tara.tahoebio.io",
            serving_client_id="offline", serving_client_secret="offline",
            databricks_host="https://example.invalid", warehouse_id="offline",
            release_id="tahoe-100m/v1", account_hmac_key=b"a"*32,
            result_handle_key=b"b"*32, state_dir=Path(directory))
        app = FastMCP("offline-public-contract")
        tools.load_tools(app, config)
        registered = await app.list_tools()
        public = {t.name: clean(t.parameters) for t in registered}
        print(json.dumps({"format_version": 1, "server_version": server_version(),
            "tools": public, "datasets": {
                "tahoe-100m": {"release": "tahoe-100m/v1", "tools": sorted(set(public)-{"health","list_releases","cancel_execution","send_feedback"}),
                    "tables": sorted(registry_view.allowed_tables()), "expression_measurements": ["raw_counts","cpm_log1p"],
                    "guide_topics": list(skills.GUIDE_TOPICS)},
                "emerald-bay": {"release": datasets.EMERALD_RELEASE, "tools": list(datasets.EMERALD_TOOLS),
                    "tables": list(datasets.EMERALD_TABLES), "expression_measurements": datasets.summary()["expression_measurements"],
                    "phenotype_measurements": datasets.summary()["phenotype_measurements"],
                    "pathway_score_kinds": datasets.summary()["pathway_score_kinds"],
                    "guide_topics": list(skills.EMERALD_GUIDE_TOPICS), "source_data_license": "CC-BY-4.0"}},
            "signatures": {"release": datasets.SIGNATURES_RELEASE, "applies_to": datasets.TAHOE,
                "tools": list(signatures.TOOLS), "guide_topics": list(skills.SIGNATURES_GUIDE_TOPICS)}}, sort_keys=True))
asyncio.run(export())
"""


def candidate_contract(server_root, interpreter):
    command = [str(interpreter), "-c", EXPORT_PROGRAM]
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    result = subprocess.run(
        command,
        cwd=server_root,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise common.RepoError(
            "offline candidate export failed; inspect the selected local environment"
        )
    contract = json.loads(result.stdout)
    for dataset in contract["datasets"].values():
        dataset["tables"] = [
            name for name in dataset["tables"] if not common.scan_text(name)
        ]
        dataset["table_alias_scope"] = (
            "public-safe documentation subset; discover full availability at runtime"
        )
    if common.scan_text(json.dumps(contract)) or common.locator_tokens(
        json.dumps(contract)
    ):
        raise common.RepoError("candidate schema export failed public-safety checks")
    return contract


def check_candidate_sql(server_root, interpreter, fixtures, shipped_calls=()):
    cases = []
    for case in fixtures["cases"]:
        if case["tool"] == "run_sql" and case["expected_route"] == "send":
            cases.append(case["arguments"])
    cases.extend(
        call["arguments"] for call in shipped_calls if call["tool"] == "run_sql"
    )
    program = """import json,sys\nfrom server.sql_policy import check\nfor args in json.load(sys.stdin):\n check(args["statement"], max_rows=args.get("max_rows",200), dataset=args.get("dataset","tahoe-100m"))\nprint("bounded SQL examples accepted by candidate policy")"""
    result = subprocess.run(
        [str(interpreter), "-c", program],
        cwd=server_root,
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        input=json.dumps(cases),
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise common.RepoError(
            "one or more bounded examples failed the candidate SQL policy"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--server-root", type=Path)
    parser.add_argument("--server-python", type=Path)
    parser.add_argument("--write-contract", action="store_true")
    parser.add_argument(
        "--fixtures-only",
        action="store_true",
        help="development check before shipped prose is updated",
    )
    args = parser.parse_args(argv)
    try:
        if args.server_root is not None:
            interpreter = (
                args.server_python or args.server_root / ".venv" / "bin" / "python"
            )
            observed = candidate_contract(args.server_root, interpreter)
            if args.write_contract:
                (args.root / CONTRACT_REL).write_text(
                    json.dumps(observed, indent=2, sort_keys=True) + "\n"
                )
            elif observed != common.load_json(args.root / CONTRACT_REL):
                raise common.RepoError(
                    "advertised candidate contract differs from public snapshot"
                )
        elif args.write_contract or args.server_python:
            raise common.RepoError(
                "candidate export requires an explicit local server root"
            )
        _, fixtures = validate_fixtures(args.root)
        shipped_calls = []
        if not args.fixtures_only:
            shipped_calls = validate_shipped_calls(args.root)
        if args.server_root is not None:
            check_candidate_sql(args.server_root, interpreter, fixtures, shipped_calls)
        print(
            "offline examples, routing requirements and schemas validated; no live host execution"
        )
        return 0
    except (common.RepoError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"example validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
