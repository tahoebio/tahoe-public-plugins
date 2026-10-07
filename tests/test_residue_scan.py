"""Residue and secret scanning.

Synthetic markers are assembled at runtime so this test file does not itself
contain the literals it looks for.
"""

from scripts import common


def _j(*parts):
    return "".join(parts)


FORBIDDEN_SAMPLES = [
    _j("s3", "://bucket/key"),
    _j("/Vol", "umes/foo"),
    _j("tahoe", "-public-mcp"),
    _j("tara", "-mcp"),
    _j("tx1", "_embeddings"),
    _j("Casp", "ian"),
    _j("dbc-", "0f17522b82e6"),
    _j("PLAN", "_v4"),
    _j("tara", ".", "internal"),
    _j("prem", "ium tier"),
    _j("Sun", "it"),
]

SECRET_SAMPLES = [
    _j("AKIA", "ABCDEFGHIJKLMNOP"),
    _j("ghp_", "A" * 40),
    _j("dapi", "0123456789abcdef0123456789abcdef"),
    _j("xoxb-", "123456789012-abcdefghij"),
    _j("-----BEGIN ", "PRIVATE KEY-----"),
    _j("api_key", ' = "', "s3cr3tvalue", '"'),
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
    _j("tahoe-public", "-mcp"),
    _j("tara", "-mcp"),
    _j("tx1", "_embeddings"),
    _j("Casp", "ian"),
    _j("Sun", "it"),
    _j("prem", "ium"),
    _j("pric", "ing"),
    _j("PLAN", "_v"),
    _j("SPEC", "_v"),
    _j("BRIEF", "_"),
    _j("_PRIV", "ATE"),
    _j(".", "internal"),
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
    (tmp_path / "note.md").write_text(_j("s3", "://example"))
    findings = common.scan_repo(tmp_path, ["note.md"])
    assert findings and findings[0]["category"] == "residue"


def test_repo_source_is_clean():
    # common.py defines the patterns and so contains their literals; it is
    # excluded from the scan by resolved-path identity, not by suppressing
    # findings in-band. This test would fail if that exclusion were removed.
    assert "scripts/common.py" in common.tracked_files()
    findings = common.scan_repo()
    assert findings == [], "\n".join(
        f"{finding['path']}:{finding['line']}: {finding['label']}"
        for finding in findings
    )
