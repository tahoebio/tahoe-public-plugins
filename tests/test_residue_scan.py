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
