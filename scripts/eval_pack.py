"""Plugin-eval scoring, disclosure, and plugin-copy retargeting.

The eval runner is not invoked here. A recording is replayed by the local
proxy only after each stored result passes the disclosure gate. That gate is
the server's three pattern classes plus the exact-field allowlist. It is not
the committed-file residue scan.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from scripts import common

SERVER_NAME = common.MCP_SERVER_NAME
RECORDING_NAME = "responses.json"
RECORDING_FORMAT = "eval-recording/1"
ALLOWLIST_REL = Path("evals") / "disclosure_allow.json"
#: Agent-facing name of a plugin MCP tool. The eval docs name those tools
#: ``mcp__plugin_<plugin>_<server>__<tool>``. ``Skill`` is a built-in.
MCP_TOOL_NAME = "mcp__plugin_{plugin}_{server}__{tool}"

# The release runner's disclosure classes. The fragment below is not the full
# atlas name. Cell codes and public table names are not in this gate.
_ATLAS_FRAGMENT = "aspian"
_INTERNAL_REF = re.compile(
    r"(?<![\w.])D\d{2,3}(?![A-Za-z0-9.])"
    r"|(?<![\w.])N\d{1,2}[a-z]?(?![A-Za-z0-9.])"
    r"|(?i:study_?\d+|notebook|\bpart ?\d\b|\bstep \d+\b)"
)
_R_NUMBER = re.compile(
    r"(?:Pearson r|\|r\|)\s*-?\d+(?:\.\d+)?(?![\d.])(?! on Tahoe-100M)"
)


class EvalError(common.RepoError):
    """The eval pack, a recording, or a results record is not acceptable."""


def scoped_mcp_tool(tool: str) -> str:
    """The name ``tool_used`` and ``tool_order`` must use for a plugin MCP tool.

    ``Skill`` is left unchanged. Every other name is ``MCP_TOOL_NAME`` filled
    from the plugin name and the MCP server name.
    """
    if tool == "Skill":
        return tool
    return MCP_TOOL_NAME.format(
        plugin=common.PLUGIN_NAME, server=common.MCP_SERVER_NAME, tool=tool
    )


def refuse_plugins_output(destination: Path, *, repo: Path | None = None) -> None:
    """Refuse an output path inside the repository ``plugins/`` tree.

    Marketplace installs copy ``plugins/``. Eval cases and mocks are rendered
    into a temporary plugin copy, never into that tree.
    """
    root = (repo or common.REPO_ROOT).resolve()
    plugins = (root / "plugins").resolve()
    dest = Path(destination).expanduser().resolve()
    if dest == plugins or plugins in dest.parents:
        raise EvalError("refusing to write eval output inside plugins/")


def scan_text(text: str) -> list[str]:
    """Pattern names that hit ``text``. Empty means the text is clean."""
    hits: list[str] = []
    if _INTERNAL_REF.search(text):
        hits.append("internal_ref")
    if _R_NUMBER.search(text):
        hits.append("r_number")
    if _ATLAS_FRAGMENT in text.lower():
        hits.append("atlas")
    return hits


# A SMILES chemical structure: only SMILES characters, no whitespace, at least
# eight characters, and at least one branch, bond or bracket symbol. A ring
# closure after a nitrogen (``C=N2)``) looks like a notebook code to the
# internal-reference pattern; a bare code such as ``D94`` is not SMILES-shaped.
_SMILES = re.compile(r"[A-Za-z0-9@+\-\[\]()=#$:/\\.%*]{8,}")
_SMILES_MARKS = frozenset("()=#[")
_SHAPES = frozenset({"smiles"})


def _is_smiles(text: str) -> bool:
    return _SMILES.fullmatch(text) is not None and any(mark in text for mark in _SMILES_MARKS)


def load_disclosure_allowlist(root: Path | None = None) -> list[dict[str, str]]:
    """The reviewed field exemptions. A bad file is an error.

    Each entry names a ``key`` and a ``pattern`` and exactly one of ``value``
    (the whole string must equal it) or ``shape`` (``smiles``: the value must
    be SMILES-shaped).
    """
    path = (root or common.REPO_ROOT) / ALLOWLIST_REL
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalError("disclosure allowlist is malformed") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("allow"), list):
        raise EvalError("disclosure allowlist is malformed")
    entries: list[dict[str, str]] = []
    for entry in payload["allow"]:
        if not isinstance(entry, dict):
            raise EvalError("disclosure allowlist is malformed")
        key, pattern = entry.get("key"), entry.get("pattern")
        if type(key) is not str or type(pattern) is not str or not key or not pattern:
            raise EvalError("disclosure allowlist is malformed")
        has_value, has_shape = "value" in entry, "shape" in entry
        if has_value == has_shape:
            raise EvalError("disclosure allowlist is malformed")
        if has_value:
            value = entry["value"]
            if type(value) is not str or not value:
                raise EvalError("disclosure allowlist is malformed")
            entries.append({"key": key, "value": value, "pattern": pattern})
        else:
            if entry["shape"] not in _SHAPES:
                raise EvalError("disclosure allowlist is malformed")
            entries.append({"key": key, "shape": entry["shape"], "pattern": pattern})
    return entries


def _entry_matches(entry: dict[str, str], key: str, item: str) -> bool:
    if entry["key"] != key:
        return False
    if "value" in entry:
        return entry["value"] == item
    return entry.get("shape") == "smiles" and _is_smiles(item)


def _field_is_exempt(key: str, item: object, allowlist: list[dict[str, str]]) -> bool:
    """True when every pattern on this field is named by an entry that matches it."""
    if type(item) is not str:
        return False
    hits = set(scan_text(item))
    if not hits:
        return False
    covered = {
        entry["pattern"]
        for entry in allowlist
        if entry["pattern"] in hits and _entry_matches(entry, key, item)
    }
    return hits <= covered


def _columnar_rows(node: dict) -> list[dict] | None:
    """Rows of a ``columns`` + ``rows`` table as named fields, or None.

    Only a table whose every row has exactly one value per column is mapped;
    anything else is scanned as written.
    """
    columns, rows = node.get("columns"), node.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        return None
    if not all(type(column) is str for column in columns):
        return None
    if not all(isinstance(row, list) and len(row) == len(columns) for row in rows):
        return None
    return [dict(zip(columns, row, strict=True)) for row in rows]


def remaining_patterns(value: object, allowlist: list[dict[str, str]]) -> list[str]:
    """Patterns left after allowed fields are ignored.

    A string is exempt only when it is an object field (or a named cell of a
    ``columns`` + ``rows`` table), an entry matches its key and its whole value
    or shape, and every pattern it hits is named by such an entry. The same
    text under another key, inside a longer string, or in a bare list is not
    exempt.
    """
    found: list[str] = []

    def add(patterns: list[str]) -> None:
        for pattern in patterns:
            if pattern not in found:
                found.append(pattern)

    def walk(node: object) -> None:
        if isinstance(node, dict):
            table = _columnar_rows(node)
            if table is not None:
                walk(table)
                node = {key: item for key, item in node.items() if key != "rows"}
            for key, item in node.items():
                if type(item) is str:
                    if not _field_is_exempt(key, item, allowlist):
                        add(scan_text(item))
                else:
                    walk(item)
        elif isinstance(node, list):
            for item in node:
                if type(item) is str:
                    add(scan_text(item))
                else:
                    walk(item)

    walk(value)
    return found


def tool_body(result: object) -> object:
    """The tool payload inside a JSON-RPC result.

    ``structuredContent`` wins. Otherwise the JSON in ``content[0].text`` is
    parsed. The text duplicate is not scanned when structured content exists.
    """
    if not isinstance(result, dict):
        return result
    if "structuredContent" in result:
        return result["structuredContent"]
    content = result.get("content")
    if isinstance(content, list) and content and isinstance(content[0], dict):
        text = content[0].get("text")
        if isinstance(text, str):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
    return result


def recording_disclosure_hits(
    recording: dict, allowlist: list[dict[str, str]] | None = None
) -> list[dict[str, object]]:
    """Hits in each stored result. An empty list means the recording is clean."""
    if allowlist is None:
        allowlist = load_disclosure_allowlist()
    hits: list[dict[str, object]] = []
    for label in ("initialize", "tools/list"):
        value = recording.get(label)
        if value is None:
            continue
        patterns = remaining_patterns(value, allowlist)
        if patterns:
            hits.append({"result": label, "patterns": patterns})
    calls = recording.get("calls")
    if isinstance(calls, dict):
        for key in sorted(calls):
            patterns = remaining_patterns(tool_body(calls[key]), allowlist)
            if patterns:
                hits.append({"result": key, "patterns": patterns})
    return hits


def _refuse_repo_plugin(copy_root: Path, repo_plugin: Path) -> Path:
    copy_root = Path(copy_root).resolve()
    repo_plugin = Path(repo_plugin).resolve()
    if copy_root == repo_plugin:
        raise EvalError("refusing to retarget the repository plugin")
    return copy_root


def _rewrite_server_urls(copy_root: Path, url: str) -> None:
    """Set every MCP server URL and drop credential fields."""
    targets = (copy_root / "mcp.json", copy_root / ".claude-plugin" / "plugin.json")
    for path in targets:
        if not path.is_file():
            raise EvalError(f"plugin copy is missing {path.name}")
        data = json.loads(path.read_text(encoding="utf-8"))
        servers = data.get("mcpServers")
        if not isinstance(servers, dict) or not servers:
            raise EvalError(f"{path.name} has no mcpServers")
        for server in servers.values():
            if not isinstance(server, dict):
                raise EvalError(f"{path.name} server entry is not an object")
            server["url"] = url
            server.pop("headers", None)
            server.pop("env", None)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def retarget_plugin_copy(copy_root: Path, url: str, *, repo_plugin: Path) -> None:
    """Point a plugin *copy* at an HTTPS ``url``. Refuses the repository plugin.

    ``url`` must be HTTPS and must not carry userinfo, a query, or a fragment.
    Credentials keys are dropped if a copy still has them.
    """
    copy_root = _refuse_repo_plugin(copy_root, repo_plugin)
    if not str(url).startswith("https://") or any(mark in url for mark in ("@", "?", "#")):
        raise EvalError("probe URL must be HTTPS without credentials or a query")
    _rewrite_server_urls(copy_root, url)


def retarget_plugin_copy_local(copy_root: Path, port: int, *, repo_plugin: Path) -> None:
    """Point a plugin *copy* at the local proxy. Refuses the repository plugin.

    ``port`` is an integer from 1 to 65535. Every server URL becomes
    ``http://127.0.0.1:<port>/mcp``. Credential fields are dropped.
    """
    copy_root = _refuse_repo_plugin(copy_root, repo_plugin)
    if type(port) is not int or not 1 <= port <= 65535:
        raise EvalError("local proxy port must be an integer from 1 to 65535")
    _rewrite_server_urls(copy_root, f"http://127.0.0.1:{port}/mcp")


# --- cases, graders, transcripts, records ---------------------------------


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Split a ``---`` block. Single-quoted scalars keep their backslashes."""
    match = common._FRONTMATTER_RE.match(text)
    if match is None:
        raise EvalError("file has no frontmatter")
    fields: dict[str, object] = {}
    for line in match.group("body").splitlines():
        key, sep, raw = line.partition(":")
        if not sep:
            continue
        fields[key.strip()] = _parse_scalar(raw.strip())
    return fields, text[match.end() :]


def _parse_scalar(raw: str) -> object:
    if len(raw) >= 2 and raw[0] == raw[-1] == "'":
        return raw[1:-1]
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        return json.loads(raw)
    if raw in {"true", "false"}:
        return raw == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    return raw


def case_tags(case_dir: Path) -> list[str]:
    fields, _body = parse_frontmatter((Path(case_dir) / "prompt.md").read_text(encoding="utf-8"))
    tags = fields.get("tags", [])
    if isinstance(tags, str):
        return [tags]
    if isinstance(tags, list):
        return [str(tag) for tag in tags]
    return []


def blocked_case_names(root: Path | None = None) -> frozenset[str]:
    """Case names the generator tags ``blocked``.

    ``root`` is unused. The catalog is the source of truth; the suite is not
    stored under ``plugins/``.
    """
    del root
    from scripts.eval_cases import all_specs

    return frozenset(spec.name for spec in all_specs() if "blocked" in spec.tags)


@dataclass
class GraderVerdict:
    name: str
    passed: bool
    reason: str
    scored: bool


@dataclass
class TranscriptScore:
    score: float
    graders: list[GraderVerdict] = field(default_factory=list)


def _grader_files(case_dir: Path) -> list[Path]:
    directory = Path(case_dir) / "graders"
    if not directory.is_dir():
        raise EvalError(f"{case_dir.name}: no graders")
    files = sorted(directory.glob("*.md"))
    if not files:
        raise EvalError(f"{case_dir.name}: no graders")
    return files


def _as_int(value: object, default: int | None) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvalError("grader bound is not an integer")
    return value


def _call_blob(call: dict) -> str:
    payload = call.get("input", {})
    if not isinstance(payload, dict):
        payload = {}
    return json.dumps(payload, sort_keys=True)


def _tool_used(fields: dict, calls: list[dict]) -> tuple[bool, str]:
    tool = str(fields.get("tool", ""))
    pattern = fields.get("input_match")
    minimum = _as_int(fields.get("min"), 1)
    maximum = _as_int(fields.get("max"), None)
    matched = []
    for call in calls:
        if call.get("tool") != tool:
            continue
        blob = _call_blob(call)
        if pattern is None or re.search(str(pattern), blob):
            matched.append(call)
    count = len(matched)
    upper = "none" if maximum is None else str(maximum)
    reason = f"{tool} calls matching the grader: {count} (min {minimum}, max {upper})"
    if minimum is not None and count < minimum:
        return False, reason
    if maximum is not None and count > maximum:
        return False, reason
    return True, reason


def _tool_order(fields: dict, calls: list[dict]) -> tuple[bool, str]:
    before = str(fields.get("before", ""))
    after = str(fields.get("after", ""))
    before_at = next((i for i, call in enumerate(calls) if call.get("tool") == before), None)
    after_at = next((i for i, call in enumerate(calls) if call.get("tool") == after), None)
    if before_at is None or after_at is None:
        return False, f"{before} before {after}: a required call is missing"
    if before_at < after_at:
        return True, f"{before} at {before_at} precedes {after} at {after_at}"
    return False, f"{before} at {before_at} does not precede {after} at {after_at}"


def _regex(fields: dict, transcript: dict) -> tuple[bool, str]:
    pattern = str(fields.get("pattern", ""))
    target = str(fields.get("target", "last_message"))
    match = str(fields.get("match", "contains"))
    calls = transcript.get("calls", [])
    if target == "last_message":
        text = str(transcript.get("last_message", ""))
    elif target == "mock_calls":
        # Tool name plus arguments. The runner shows both; the name is not
        # inside the argument object, so a route check can see it.
        text = "\n".join(
            f"{call.get('tool', '')} {_call_blob(call)}" for call in calls
        )
    else:
        text = json.dumps(transcript, sort_keys=True)
    found = re.search(pattern, text) is not None
    if match == "not_contains":
        passed = not found
    else:
        passed = found
    return passed, f"pattern {'found' if found else 'absent'} under match {match}"


def score_transcript(case_dir: Path, transcript: dict) -> TranscriptScore:
    """Score deterministic graders. A failing ``max: 0`` grader forces score 0.

    ``llm`` graders are reported and not scored: this function does not call a
    judge. Score 0 from a forbidden call is therefore not a judge result.
    """
    calls = transcript.get("calls", [])
    if not isinstance(calls, list):
        raise EvalError("transcript calls must be a list")
    verdicts: list[GraderVerdict] = []
    forced_zero = False
    for path in _grader_files(case_dir):
        fields, _body = parse_frontmatter(path.read_text(encoding="utf-8"))
        kind = str(fields.get("type", ""))
        if kind == "llm":
            verdicts.append(
                GraderVerdict(path.stem, False, "judge grader not run offline", scored=False)
            )
            continue
        if kind == "tool_used":
            passed, reason = _tool_used(fields, calls)
            if _as_int(fields.get("max"), None) == 0 and not passed:
                forced_zero = True
        elif kind == "tool_order":
            passed, reason = _tool_order(fields, calls)
        elif kind == "regex":
            passed, reason = _regex(fields, transcript)
        else:
            raise EvalError(f"{path.name}: unsupported grader type {kind}")
        verdicts.append(GraderVerdict(path.stem, passed, reason, scored=True))
    scored = [item for item in verdicts if item.scored]
    if not scored or forced_zero:
        score = 0.0
    else:
        score = sum(1 for item in scored if item.passed) / len(scored)
    return TranscriptScore(score, verdicts)


def _grader_rows(case: dict) -> list[dict]:
    rows = []
    seen: list[dict] = []
    if isinstance(case.get("graders"), list):
        seen.extend(case["graders"])
    arms = case.get("arms") if isinstance(case.get("arms"), dict) else {}
    for arm in arms.get("with", []) if isinstance(arms.get("with"), list) else []:
        if isinstance(arm, dict) and isinstance(arm.get("graders"), list):
            seen.extend(arm["graders"])
    for item in seen:
        if not isinstance(item, dict):
            continue
        reason = item.get("reason", item.get("explanation", item.get("message", "")))
        passed = item.get("passed", item.get("pass"))
        rows.append(
            {
                "name": str(item.get("name", "")),
                "passed": bool(passed),
                "reason": "" if reason is None else str(reason),
            }
        )
    return rows


def record_from_aggregate(aggregate: dict, *, root: Path | None = None) -> dict:
    """Convert a runner aggregate into a results record.

    A case tagged ``blocked`` in the suite is recorded as ``blocked`` even when
    the runner score is perfect. It is not placed in ``passed``.
    """
    if not isinstance(aggregate, dict):
        raise EvalError("aggregate is not an object")
    blocked = blocked_case_names(root)
    cases = []
    passed: list[str] = []
    for item in aggregate.get("cases") or []:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise EvalError("aggregate case is missing a name")
        name = item["name"]
        graders = _grader_rows(item)
        aborted = False
        arms = item.get("arms") if isinstance(item.get("arms"), dict) else {}
        for run in arms.get("with", []) if isinstance(arms.get("with"), list) else []:
            if isinstance(run, dict) and run.get("aborted"):
                aborted = True
        score = None
        aggregates = item.get("aggregates")
        if isinstance(aggregates, dict):
            score = aggregates.get("score")
        if name in blocked:
            status = "blocked"
        elif aborted or not isinstance(score, (int, float)) or float(score) < 1.0:
            status = "fail"
        else:
            status = "pass"
            passed.append(name)
        cases.append({"name": name, "status": status, "graders": graders})
    return {
        "schema_version": 1,
        "partial": bool(aggregate.get("partial")),
        "partial_reason": aggregate.get("partialReason") or aggregate.get("partial_reason"),
        "runner_version": aggregate.get("claudeVersion"),
        "passed": passed,
        "cases": cases,
    }


def record_problems(record: dict, *, root: Path | None = None) -> list[str]:
    """Problems that make a record unacceptable. Empty means it may be kept.

    A blocked case with status ``pass``, a blocked name in ``passed``, or a
    partial run is refused. An honest fail is not.
    """
    if not isinstance(record, dict) or not isinstance(record.get("cases"), list):
        return ["record has no cases"]
    problems: list[str] = []
    if record.get("partial") is True:
        reason = record.get("partial_reason") or "partial"
        problems.append(f"partial run: {reason}")
    blocked = blocked_case_names(root)
    for name in record.get("passed") or []:
        if name in blocked:
            problems.append(f"{name}: blocked case counted as pass")
    for case in record["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("name"), str):
            problems.append("a case is missing a name")
            continue
        name = case["name"]
        status = case.get("status")
        if name in blocked and status == "pass":
            problems.append(f"{name}: blocked case counted as pass")
        graders = case.get("graders")
        if graders is None:
            problems.append(f"{name}: missing grader reasons")
            continue
        if not isinstance(graders, list):
            problems.append(f"{name}: grader reasons are not a list")
            continue
        for grader in graders:
            if not isinstance(grader, dict) or "reason" not in grader:
                problems.append(f"{name}: a grader is missing its reason")
                break
    return problems


def format_record(record: dict) -> str:
    """One line per case: name, status, and each grader reason."""
    lines = []
    for case in record.get("cases", []):
        reasons = []
        for grader in case.get("graders") or []:
            if isinstance(grader, dict):
                reasons.append(f"{grader.get('name', '')}: {grader.get('reason', '')}")
        detail = "; ".join(reasons) if reasons else "(no grader reasons)"
        lines.append(f"{case.get('name', '')}\t{case.get('status', '')}\t{detail}")
    return "\n".join(lines)
