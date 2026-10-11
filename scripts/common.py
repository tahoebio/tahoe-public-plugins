"""Shared helpers for validation, residue scanning and packaging.

Scans are textual: they cover tracked files, the built archive and git history,
and report content that cannot be read as text rather than skipping it. Nothing
here reads, writes or prints credentials.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import re
import subprocess
import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"

#: Single source of truth for the marketplace, plugin and remote-server identity.
PLUGIN_NAME = "tara"
MARKETPLACE_NAME = "tahoe-public"
MARKETPLACE_DISPLAY_NAME = "Tahoe Bio Plugins"
#: The remote MCP server is named for the public service, never for the plugin:
#: ``tara`` names a different, internal service.
MCP_SERVER_NAME = "tahoe-public"
MCP_ENDPOINT = "https://tara.tahoebio.io/mcp"

#: Plugin-root files. The portable manifest and MCP config are what Codex
#: reads; the native adapter is Claude's own manifest, with MCP inline.
PLUGIN_MANIFEST_REL = f"plugins/{PLUGIN_NAME}/plugin.json"
MCP_CONFIG_REL = f"plugins/{PLUGIN_NAME}/mcp.json"
CLAUDE_ADAPTER_REL = f"plugins/{PLUGIN_NAME}/.claude-plugin/plugin.json"

#: Repository catalogs. The two hosts use different shapes, so these are not
#: byte-identical; they must agree on identity and source instead.
CODEX_CATALOG_REL = ".agents/plugins/marketplace.json"
CLAUDE_CATALOG_REL = ".claude-plugin/marketplace.json"
MARKETPLACE_PATHS = (CODEX_CATALOG_REL, CLAUDE_CATALOG_REL)
INSTALLATION_POLICIES = frozenset(
    {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"}
)
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

#: The exact files that make up the release archive. An explicit list, not a
#: directory prefix: the plugin ships connection manifests and nothing else.
#: Dotfiles are permitted only by being named here.
ARCHIVE_ALLOWLIST = (PLUGIN_MANIFEST_REL, MCP_CONFIG_REL, CLAUDE_ADAPTER_REL)

GENERATED_DIRS = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".venv",
        "node_modules",
        "dist",
    }
)
GENERATED_SUFFIXES = (".pyc", ".pyo", ".zip", ".sha256", ".egg-info")

#: Paths the repository layout is required to contain.
REQUIRED_LAYOUT = (
    "README.md",
    "AGENTS.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    ".gitignore",
    ".agents/plugins/marketplace.json",
    ".claude-plugin/marketplace.json",
    PLUGIN_MANIFEST_REL,
    MCP_CONFIG_REL,
    CLAUDE_ADAPTER_REL,
    "docs/install.md",
    "docs/install-verification.md",
    "docs/public-tool-contract.md",
    "docs/compatibility.md",
    "docs/data-and-licensing.md",
    "docs/releasing.md",
    "scripts/validate.py",
    "scripts/package.py",
    "scripts/sweep_branches.py",
    ".github/workflows/ci.yml",
    ".github/workflows/sweep.yml",
)

class RepoError(Exception):
    """A repository invariant was violated."""


class PackagingError(RepoError):
    """A release archive could not be built safely."""


class ResidueError(RepoError):
    """Forbidden internal residue or a secret was found in tracked files."""


def _frag(*parts: str) -> str:
    """Join fragments so no forbidden literal is contiguous in source.

    This pattern table is a tracked, public file. Every literal it looks for —
    internal names (repos, a non-public dataset, an excluded table, a person,
    commercial-tier wording) and generic shapes (object-store URIs, volume
    paths) — is assembled at import time, so this file contains none of them and
    is scanned like any other file.
    """
    return "".join(parts)


# Internal residue that must never reach a public artifact. Every pattern is
# assembled from fragments so this file contains no contiguous forbidden
# literal, and is therefore scanned like any other file rather than excluded.
FORBIDDEN_PATTERNS = [
    ("internal-object-store-uri", re.compile(_frag("s3", "://"))),
    ("internal-volume-path", re.compile(_frag("/Vol", "umes/"))),
    ("private-service-repo", re.compile(_frag("tahoe-public", "-mcp"))),
    ("internal-mcp-repo", re.compile(_frag("tara", "-mcp"))),
    ("excluded-table-name", re.compile(_frag("tx1", "_embeddings"))),
    ("non-public-dataset", re.compile(_frag("Casp", "ian"), re.I)),
    ("databricks-host-id", re.compile(r"dbc-[0-9a-f]{6,}")),
    (
        "private-planning-doc",
        re.compile(
            "|".join(
                (
                    _frag("PLAN", "_v[0-9]"),
                    _frag("SPEC", "_v[0-9]"),
                    _frag("BRIEF", "_"),
                    _frag("_PRIV", "ATE"),
                )
            )
        ),
    ),
    ("internal-hostname", re.compile(_frag(r"\.", "internal", r"\b"))),
    (
        "commercial-tier-language",
        re.compile(
            "(?i)\\b("
            + "|".join((_frag("prem", "ium"), _frag("pric", "ing")))
            + ")\\b"
        ),
    ),
    ("person-name", re.compile(r"\b" + _frag("Sun", "it") + r"\b")),
]

# Secret shapes. These are heuristics, not a substitute for human review.
SECRET_PATTERNS = [
    ("aws-access-key-id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("databricks-pat", re.compile(r"dapi[0-9a-f]{32}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "secret-assignment",
        re.compile(
            r"""\b(api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*["'][^"'\s]{8,}["']""",
            re.I,
        ),
    ),
]

_PATTERN_GROUPS = (("residue", FORBIDDEN_PATTERNS), ("secret", SECRET_PATTERNS))


def plugin_dir(root: Path = REPO_ROOT) -> Path:
    return root / "plugins" / PLUGIN_NAME


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_schema(name: str) -> dict:
    return load_json(SCHEMA_DIR / f"{name}.schema.json")


def tracked_files(root: Path = REPO_ROOT) -> list[str]:
    """Return tracked files, sorted, relative to ``root`` (git index order)."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(line for line in result.stdout.splitlines() if line)


def _match_line(line: str) -> list[tuple[str, str]]:
    """Return ``(category, label)`` for every pattern that matches ``line``."""
    return [
        (category, label)
        for category, patterns in _PATTERN_GROUPS
        for label, regex in patterns
        if regex.search(line)
    ]


def scan_text(text: str) -> list[tuple[str, str, int, str]]:
    """Return ``(category, label, line_number, line)`` for every finding."""
    return [
        (category, label, lineno, line.strip())
        for lineno, line in enumerate(text.splitlines(), start=1)
        for category, label in _match_line(line)
    ]


def _finding(
    source: str, path: str, category: str, label: str, lineno: int, line: str
) -> dict:
    return {
        "source": source,
        "path": path,
        "category": category,
        "label": label,
        "line": lineno,
        "text": line.strip(),
        #: The commit an added line came from, when a history scan supplies it.
        "commit": "",
    }


def _unscannable(source: str, path: str) -> dict:
    """A member that cannot be read as text is reported, never skipped."""
    return _finding(source, path, "unscannable", "unscannable-file", 0, "")


def _scan_lines(
    source: str, path: str, numbered_lines: Iterable[tuple[int, str]]
) -> list[dict]:
    """Scan ``(line_number, text)`` pairs from one file and build findings."""
    findings: list[dict] = []
    for lineno, text in numbered_lines:
        for category, label in _match_line(text):
            findings.append(_finding(source, path, category, label, lineno, text))
    return findings


def format_findings(findings: Iterable[dict]) -> str:
    """Render findings as indented ``[source] path:line: label`` lines."""
    return "\n".join(
        f"  [{finding['source']}] {finding['path']}:{finding['line']}: "
        f"{finding['label']}"
        for finding in findings
    )


def scan_repo(
    root: Path = REPO_ROOT, rel_paths: list[str] | None = None
) -> list[dict]:
    """Scan tracked files (or an explicit list) and return findings as dicts."""
    paths = tracked_files(root) if rel_paths is None else rel_paths
    findings: list[dict] = []
    for rel in paths:
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(_unscannable("worktree", rel))
            continue
        except OSError:
            continue
        findings.extend(_scan_lines("worktree", rel, enumerate(text.splitlines(), 1)))
    return findings


def scan_archive(path: Path) -> list[dict]:
    """Scan the text members of a built zip archive for residue and secrets."""
    findings: list[dict] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            try:
                text = archive.read(name).decode("utf-8")
            except UnicodeDecodeError:
                findings.append(_unscannable("archive", name))
                continue
            findings.extend(
                _scan_lines("archive", name, enumerate(text.splitlines(), 1))
            )
    return findings


#: Commit headers and the end of a commit message carry markers that no diff
#: line can produce (added lines start with ``+``), so an added line of exactly
#: 40 hex characters is never mistaken for a commit header.
_HISTORY_COMMIT = "@@commit@@"
_HISTORY_MESSAGE_END = "@@message-end@@"
_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _git_output(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True
    )


def _is_git_repo(root: Path) -> bool:
    result = _git_output(root, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def require_full_history(root: Path = REPO_ROOT) -> None:
    """Raise unless ``root`` carries the full history the scan needs.

    A scan that cannot read history must fail rather than report clean.
    """
    if not _is_git_repo(root):
        raise RepoError("history scan requires a git repository")
    shallow = _git_output(root, "rev-parse", "--is-shallow-repository")
    if shallow.stdout.strip() == "true":
        raise RepoError(
            "history scan requires the full history; this is a shallow clone"
        )


def _diff_path(line: str) -> str:
    """Return the ``b/`` path from a ``diff --git a/… b/…`` line."""
    _, _, tail = line.partition(" b/")
    return tail


def _scannable_lines(
    stream: Iterable[str],
) -> Iterator[tuple[str, int, str | None, str]]:
    """Yield ``(path, line_number, text, commit)`` for everything a history scan
    reads.

    Covers added lines, commit messages (as public as the diff, so scanned under
    a ``commit <sha>`` path) and binary-change notices, for which ``text`` is
    ``None`` — a binary member cannot be read as text and is reported, not
    skipped. ``commit`` is the commit the line belongs to, so a finding can name
    the commit that introduced it.
    """
    path = ""
    lineno = 0
    commit = ""
    in_message = False
    in_hunk = False
    for raw in stream:
        line = raw.rstrip("\n")
        if line.startswith(_HISTORY_COMMIT):
            in_message, in_hunk = True, False
            commit = line[len(_HISTORY_COMMIT) :]
            path = f"commit {commit[:12]}"
            lineno = 0
            continue
        if in_message:
            if line == _HISTORY_MESSAGE_END:
                in_message, path = False, ""
                continue
            lineno += 1
            yield path, lineno, line, commit
            continue
        header = _HUNK_HEADER.match(line)
        if header:
            lineno, in_hunk = int(header.group(1)), True
            continue
        if line.startswith("diff --git "):
            in_hunk, path = False, _diff_path(line)
            continue
        if not in_hunk:
            if line.startswith("+++ b/"):
                path = line[len("+++ b/") :]
            elif line.startswith("Binary files ") and line.endswith(" differ"):
                yield path, 0, None, commit
            continue
        if line.startswith("+"):
            yield path, lineno, line[1:], commit
            lineno += 1
        elif line.startswith(" "):
            lineno += 1


def _history_selector(ref: str | None, all_refs: bool) -> list[str]:
    """The ``git log`` revision selector for a history scan."""
    return ["--all"] if all_refs else [ref or "HEAD"]


def scan_history(
    root: Path = REPO_ROOT, *, ref: str | None = None, all_refs: bool = False
) -> list[dict]:
    """Scan every line added, every commit message and every binary change.

    Scans the history reachable from ``ref`` (default ``HEAD``), so a scan is a
    function of the commit under test and not of whatever other branches happen
    to be fetched. ``all_refs=True`` restores the whole-repository sweep over
    every ref — a developer convenience, and the pre-publication sweep's engine;
    it is never the CI default, because one stale branch would otherwise fail
    every unrelated branch and ``main``.

    Returns ``[]`` when ``root`` is not a git repository, or has no commits.
    """
    if not _is_git_repo(root):
        return []
    if not all_refs and _git_output(root, "rev-parse", "--verify", "HEAD").returncode:
        return []

    command = [
        "git",
        "-C",
        str(root),
        "-c",
        "core.quotePath=false",
        "log",
        # --full-history: do not let path-history simplification drop a commit on
        # a merged parent whose change a merge resolution reverted. The scan must
        # cover the ref's FULL ancestry, every merge parent included.
        "--full-history",
        *_history_selector(ref, all_refs),
        "-p",
        "--no-color",
        f"--format={_HISTORY_COMMIT}%H%n%B%n{_HISTORY_MESSAGE_END}",
        "--",
        ".",
    ]
    with subprocess.Popen(command, stdout=subprocess.PIPE, text=True) as process:
        lines = _scannable_lines(process.stdout)
        findings: list[dict] = []
        for path, group in itertools.groupby(lines, key=lambda entry: entry[0]):
            entries = list(group)
            binary = next((entry for entry in entries if entry[2] is None), None)
            if binary is not None:
                finding = _unscannable("history", path)
                finding["commit"] = binary[3]
                findings.append(finding)
                continue
            for _, lineno, text, commit in entries:
                for category, label in _match_line(text):
                    finding = _finding(
                        "history", path, category, label, lineno, text
                    )
                    finding["commit"] = commit
                    findings.append(finding)
    if process.returncode:
        raise RepoError(f"git log failed while scanning history ({process.returncode})")
    return findings


def _is_generated(rel: str) -> bool:
    parts = Path(rel).parts
    if any(part in GENERATED_DIRS for part in parts):
        return True
    return any(part.endswith(GENERATED_SUFFIXES) for part in parts)


def _resolved_member(root: Path, rel: str) -> Path:
    """Resolve ``rel`` under ``root``, refusing symlinks and escapes.

    Every component is checked, not only the final one: a symlinked *parent*
    directory would otherwise let a member resolve to a file outside the
    checkout.
    """
    root_resolved = Path(root).resolve()
    current = root_resolved
    for part in Path(rel).parts:
        current = current / part
        if current.is_symlink():
            raise PackagingError(f"refusing to package symlinked path: {rel}")
    resolved = current.resolve()
    if not resolved.is_relative_to(root_resolved):
        raise PackagingError(f"refusing to package path outside the root: {rel}")
    return resolved


def collect_archive_members(root: Path, rel_paths: list[str]) -> list[str]:
    """Return the allowlisted manifest files, refusing unsafe or missing ones.

    The archive is an exact list, so an unlisted file — hidden or not — is
    simply excluded; only the named manifests are checked for safety.
    """
    tracked = set(rel_paths)
    members: list[str] = []
    for rel in sorted(ARCHIVE_ALLOWLIST):
        if rel not in tracked:
            raise PackagingError(f"allowlisted file is not tracked: {rel}")
        if _is_generated(rel):
            raise PackagingError(f"refusing to package generated path: {rel}")
        _resolved_member(root, rel)
        members.append(rel)
    return members


def build_archive(root: Path, members: list[str], out_path: Path) -> Path:
    """Write a deterministic zip of ``members`` and return its path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for rel in members:
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (root / rel).read_bytes())
    return out_path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksum(path: Path) -> Path:
    out = Path(str(path) + ".sha256")
    out.write_text(f"{sha256_file(path)}  {Path(path).name}\n", encoding="utf-8")
    return out


def pyproject_version(root: Path = REPO_ROOT) -> str:
    """Return the version declared in pyproject.toml ``[project]``."""
    text = (root / "pyproject.toml").read_text(encoding="utf-8").split("[project]", 1)[1]
    project = text.split("[", 1)[0]
    match = re.search(r'^version\s*=\s*"([^"]+)"', project, re.MULTILINE)
    if not match:
        raise RepoError("pyproject.toml [project] has no version")
    return match.group(1)
