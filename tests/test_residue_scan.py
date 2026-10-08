"""Residue and secret scanning.

Synthetic markers are assembled at runtime so this test file does not itself
contain the literals it looks for.
"""

import zipfile

from helpers import commit_all, git_repo, j
from scripts import common

FORBIDDEN_SAMPLES = [
    j("s3", "://bucket/key"),
    j("/Vol", "umes/foo"),
    j("tahoe", "-public-mcp"),
    j("tara", "-mcp"),
    j("tx1", "_embeddings"),
    j("Casp", "ian"),
    j("dbc-", "0f17522b82e6"),
    j("PLAN", "_v4"),
    j("tara", ".", "internal"),
    j("prem", "ium tier"),
    j("Sun", "it"),
]

SECRET_SAMPLES = [
    j("AKIA", "ABCDEFGHIJKLMNOP"),
    j("ghp_", "A" * 40),
    j("dapi", "0123456789abcdef0123456789abcdef"),
    j("xoxb-", "123456789012-abcdefghij"),
    j("-----BEGIN ", "PRIVATE KEY-----"),
    j("api_key", ' = "', "s3cr3tvalue", '"'),
]


def test_scanner_flags_synthetic_forbidden_markers():
    for sample in FORBIDDEN_SAMPLES:
        assert common.scan_text(sample), f"not flagged: {sample!r}"


def test_scanner_flags_synthetic_secret_markers():
    for sample in SECRET_SAMPLES:
        assert common.scan_text(sample), f"not flagged: {sample!r}"


# Literals the public repo must never contain. Assembled from fragments so this
# test file does not itself contain them.
FORBIDDEN_LITERALS = [
    j("tahoe-public", "-mcp"),
    j("tara", "-mcp"),
    j("tx1", "_embeddings"),
    j("Casp", "ian"),
    j("Sun", "it"),
    j("prem", "ium"),
    j("pric", "ing"),
    j("PLAN", "_v"),
    j("SPEC", "_v"),
    j("BRIEF", "_"),
    j("_PRIV", "ATE"),
    j(".", "internal"),
]


def test_tracked_tree_contains_no_forbidden_literals():
    """No tracked file may contain an internal/private name, even in the scanner
    that looks for it. This scans raw file contents directly (not via
    ``scan_repo``, which excludes the pattern module) so the pattern table
    itself is covered."""
    hits = []
    for rel in common.tracked_files():
        text = (common.REPO_ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        for literal in FORBIDDEN_LITERALS:
            if literal in text:
                hits.append(f"{rel}: {literal!r}")
    assert hits == [], hits


def test_scan_repo_flags_marker_in_explicit_file_list(tmp_path):
    (tmp_path / "note.md").write_text(j("s3", "://example"))
    findings = common.scan_repo(tmp_path, ["note.md"])
    assert findings and findings[0]["category"] == "residue"


def test_repo_source_is_clean():
    # common.py defines the patterns and so contains their literals; it is
    # excluded from the scan by resolved-path identity, not by suppressing
    # findings in-band. This test would fail if that exclusion were removed.
    assert "scripts/common.py" in common.tracked_files()
    findings = common.scan_repo()
    assert findings == [], common.format_findings(findings)


def test_scan_archive_flags_planted_marker(tmp_path):
    archive = tmp_path / "planted.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("plugins/tara/note.md", j("s3", "://bucket/key") + "\n")
    findings = common.scan_archive(archive)
    assert findings and findings[0]["category"] == "residue"
    assert findings[0]["path"] == "plugins/tara/note.md"


def test_scan_archive_clean_archive(tmp_path):
    archive = tmp_path / "clean.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("plugins/tara/plugin.json", '{"name": "tara"}\n')
    assert common.scan_archive(archive) == []


def test_scan_history_flags_planted_marker(tmp_path):
    repo = git_repo(tmp_path)
    (repo / "note.md").write_text(j("Casp", "ian") + "\n")
    commit_all(repo)
    findings = common.scan_history(repo)
    assert findings and findings[0]["category"] == "residue"
    assert findings[0]["path"] == "note.md"


def test_scan_history_reports_the_added_line_number(tmp_path):
    repo = git_repo(tmp_path)
    (repo / "note.md").write_text("first\n" + j("s3", "://bucket") + "\n")
    commit_all(repo)
    findings = common.scan_history(repo)
    assert [finding["line"] for finding in findings] == [2]


def test_scan_history_flags_marker_in_a_commit_message(tmp_path):
    repo = git_repo(tmp_path)
    (repo / "note.md").write_text("plain\n")
    commit_all(repo, message=j("s3", "://bucket") + " in the message")
    findings = common.scan_history(repo)
    assert findings and findings[0]["path"].startswith("commit ")


def test_scan_history_ignores_non_git_directory(tmp_path):
    (tmp_path / "note.md").write_text("plain\n")
    assert common.scan_history(tmp_path) == []


def test_repo_history_is_clean():
    findings = common.scan_history()
    assert findings == [], common.format_findings(findings)
