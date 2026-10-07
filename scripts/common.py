"""Shared helpers for validation, residue scanning and packaging.

Scans are textual and operate on tracked files only. Nothing here reads, writes
or prints credentials.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"

#: Single source of truth for the marketplace and plugin identity.
PLUGIN_NAME = "tara"
MARKETPLACE_NAME = "tahoe-public"
MARKETPLACE_DISPLAY_NAME = "Tahoe Bio Plugins"
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
    f"plugins/{PLUGIN_NAME}/skills/{PLUGIN_NAME}/SKILL.md",
    "docs/install.md",
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
#: real secret anywhere.
_SCANNER_MODULE = Path(__file__).resolve()


class RepoError(Exception):
    """A repository invariant was violated."""


class PackagingError(RepoError):
    """A release archive could not be built safely."""


class ResidueError(RepoError):
    """Forbidden internal residue or a secret was found in tracked files."""


# Internal residue that must never reach a public artifact.
FORBIDDEN_PATTERNS = [
    ("internal-object-store-uri", re.compile(r"s3://")),
    ("internal-volume-path", re.compile(r"/Volumes/")),
    ("private-service-repo", re.compile(r"tahoe-public-mcp")),
    ("internal-mcp-repo", re.compile(r"tara-mcp")),
    ("excluded-table-name", re.compile(r"tx1_embeddings")),
    ("non-public-dataset", re.compile(r"Caspian", re.I)),
    ("databricks-host-id", re.compile(r"dbc-[0-9a-f]{6,}")),
    ("private-planning-doc", re.compile(r"(PLAN_v[0-9]|_PRIVATE|SPEC_v[0-9]|BRIEF_)")),
    ("internal-hostname", re.compile(r"\.internal\b")),
    ("commercial-tier-language", re.compile(r"(?i)\b(premium|pricing)\b")),
    ("person-name", re.compile(r"\bSunit\b")),
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
        for category, label, lineno, line in scan_text(text):
            findings.append(
                {
                    "path": rel,
                    "category": category,
                    "label": label,
                    "line": lineno,
                    "text": line,
                }
            )
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
