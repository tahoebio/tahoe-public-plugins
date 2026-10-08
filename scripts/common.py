"""Shared helpers for validation, residue scanning and packaging.

Scans are textual and operate on tracked files only. Nothing here reads, writes
or prints credentials.
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
MCP_CONFIG_REL = f"plugins/{PLUGIN_NAME}/mcp.json"
MARKETPLACE_PATHS = (
    ".agents/plugins/marketplace.json",
    ".claude-plugin/marketplace.json",
)
INSTALLATION_POLICIES = frozenset(
    {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"}
)
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

#: Only files under these prefixes may enter a release archive.
ARCHIVE_ALLOWLIST = (f"plugins/{PLUGIN_NAME}/",)

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
    f"plugins/{PLUGIN_NAME}/plugin.json",
    MCP_CONFIG_REL,
    f"plugins/{PLUGIN_NAME}/skills/{PLUGIN_NAME}/SKILL.md",
    "docs/install.md",
    "docs/install-verification.md",
    "docs/public-tool-contract.md",
    "docs/compatibility.md",
    "docs/data-and-licensing.md",
    "docs/releasing.md",
    "scripts/validate.py",
    "scripts/package.py",
    ".github/workflows/ci.yml",
)

#: This module defines the patterns below, so it necessarily contains their
#: literals. It is excluded from scanning by resolved-path identity — a narrow,
#: reviewable exclusion rather than a per-line suppression that could hide a
#: real secret anywhere. The same exclusion applies to the history scan, for the
#: same reason.
_SCANNER_MODULE = Path(__file__).resolve()


class RepoError(Exception):
    """A repository invariant was violated."""


class PackagingError(RepoError):
    """A release archive could not be built safely."""


class ResidueError(RepoError):
    """Forbidden internal residue or a secret was found in tracked files."""


def _frag(*parts: str) -> str:
    """Join fragments so a sensitive name is never contiguous in source.

    This pattern table is a tracked, public file. Names that must not appear in
    the public repo (internal repos, a non-public dataset, an excluded table, a
    person, commercial-tier wording) are assembled at import time so the file
    does not itself contain the strings the scanner looks for.
    """
    return "".join(parts)


# Internal residue that must never reach a public artifact. Sensitive names are
# assembled from fragments; generic shapes (secrets, object-store URIs, volume
# paths, host-id shapes) are written literally.
FORBIDDEN_PATTERNS = [
    ("internal-object-store-uri", re.compile(r"s3" "://")),
    ("internal-volume-path", re.compile(r"/Vol" "umes/")),
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


def scan_text(text: str) -> list[tuple[str, str, int, str]]:
    """Return ``(category, label, line_number, line)`` for every finding."""
    findings: list[tuple[str, str, int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for category, patterns in _PATTERN_GROUPS:
            for label, regex in patterns:
                if regex.search(line):
                    findings.append((category, label, lineno, line.strip()))
    return findings


def _finding(
    source: str, path: str, category: str, label: str, lineno: int, line: str
) -> dict:
    return {
        "source": source,
        "path": path,
        "category": category,
        "label": label,
        "line": lineno,
        "text": line,
    }


def _scan_lines(
    source: str, path: str, numbered_lines: Iterable[tuple[int, str]]
) -> list[dict]:
    """Scan ``(line_number, text)`` pairs from one file and build findings."""
    findings: list[dict] = []
    for lineno, text in numbered_lines:
        for category, label, _, line in scan_text(text):
            findings.append(_finding(source, path, category, label, lineno, line))
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
        path = root / rel
        try:
            if path.resolve() == _SCANNER_MODULE:
                continue
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
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
            except (UnicodeDecodeError, KeyError):
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


def _is_git_repo(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _scanner_exclusion(root: Path) -> list[str]:
    """Pathspec excluding the scanner module, relative to ``root`` if it holds it."""
    try:
        rel = _SCANNER_MODULE.relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return []
    return [f":(exclude){rel}"]


def _scannable_lines(stream: Iterable[str]) -> Iterator[tuple[str, int, str]]:
    """Yield ``(path, line_number, text)`` for added lines and commit messages.

    Commit messages are as public as the diff, so they are scanned too, under a
    ``commit <sha>`` path.
    """
    path = ""
    lineno = 0
    in_message = False
    for raw in stream:
        line = raw.rstrip("\n")
        if line.startswith(_HISTORY_COMMIT):
            in_message = True
            path = f"commit {line[len(_HISTORY_COMMIT) :][:12]}"
            lineno = 0
            continue
        if in_message:
            if line == _HISTORY_MESSAGE_END:
                in_message = False
                path = ""
                continue
            lineno += 1
            yield path, lineno, line
            continue
        if line.startswith("+++ b/"):
            path = line[len("+++ b/") :]
            continue
        header = _HUNK_HEADER.match(line)
        if header:
            lineno = int(header.group(1))
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            yield path, lineno, line[1:]
            lineno += 1
        elif line.startswith(" "):
            lineno += 1


def scan_history(root: Path = REPO_ROOT) -> list[dict]:
    """Scan every line added and every commit message in git history.

    Returns ``[]`` when ``root`` is not a git repository. The scanner module is
    excluded by path for the same reason the working-tree scan excludes it.
    """
    if not _is_git_repo(root):
        return []

    command = [
        "git",
        "-C",
        str(root),
        "-c",
        "core.quotePath=false",
        "log",
        "--all",
        "-p",
        "--no-color",
        f"--format={_HISTORY_COMMIT}%H%n%B{_HISTORY_MESSAGE_END}",
        "--",
        ".",
        *_scanner_exclusion(root),
    ]
    with subprocess.Popen(
        command, stdout=subprocess.PIPE, text=True
    ) as process:
        lines = _scannable_lines(process.stdout)
        findings: list[dict] = []
        for path, group in itertools.groupby(lines, key=lambda entry: entry[0]):
            findings.extend(
                _scan_lines("history", path, ((ln, tx) for _, ln, tx in group))
            )
    if process.returncode:
        raise RepoError(f"git log failed while scanning history ({process.returncode})")
    return findings


def _is_hidden(rel: str) -> bool:
    return any(part.startswith(".") for part in Path(rel).parts)


def _is_generated(rel: str) -> bool:
    parts = Path(rel).parts
    if any(part in GENERATED_DIRS for part in parts):
        return True
    return any(part.endswith(GENERATED_SUFFIXES) for part in parts)


def collect_archive_members(root: Path, rel_paths: list[str]) -> list[str]:
    """Select archive members, refusing anything unsafe or out of scope."""
    members: list[str] = []
    for rel in sorted(rel_paths):
        if not rel.startswith(ARCHIVE_ALLOWLIST):
            continue
        path = root / rel
        if path.is_symlink():
            raise PackagingError(f"refusing to package symlink: {rel}")
        if _is_hidden(rel):
            raise PackagingError(f"refusing to package hidden path: {rel}")
        if _is_generated(rel):
            raise PackagingError(f"refusing to package generated path: {rel}")
        members.append(rel)
    if not members:
        raise PackagingError("no allowlisted files to package")
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
