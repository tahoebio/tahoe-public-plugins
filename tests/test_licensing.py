"""The licensing statement exists, is consistent, and is no longer a placeholder.

The decision: plugin code is Apache-2.0; the skill text and the documentation
are CC BY 4.0; the Tahoe-100M dataset the service serves is CC0-1.0.
"""

from scripts import common

ROOT = common.REPO_ROOT

#: Wording that belonged to the pre-decision placeholder state. None of it may
#: survive in a file that states the licensing position.
STALE_PHRASES = (
    "placeholder",
    "no licence has been chosen",
    "no license file",
    "licensing is unresolved",
    "unresolved licence",
    "do not add a `license",
)

#: The files that state the licensing position.
LICENSING_DOCS = (
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "docs/data-and-licensing.md",
    "docs/releasing.md",
    "plugins/tara/assets/README.md",
)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text()


def test_license_file_is_the_apache_2_text():
    text = _read("LICENSE")
    assert "Apache License" in text
    assert "Version 2.0, January 2004" in text
    assert "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION" in text


def test_cc_by_license_file_is_the_cc_by_4_text():
    text = _read("LICENSE-CC-BY-4.0")
    assert "Attribution 4.0 International" in text
    assert "Creative Commons Attribution 4.0 International Public License" in text
    assert "Section 2 -- Scope." in text


def test_notice_carries_attribution_and_points_at_both_licences():
    text = _read("NOTICE")
    assert "Tahoe Bio" in text
    assert "Apache-2.0" in text and "CC BY 4.0" in text
    assert "LICENSE" in text and "LICENSE-CC-BY-4.0" in text


def test_readme_names_the_file_licence_map():
    text = _read("README.md")
    assert "skills/**" in text and "docs/**" in text
    assert "CC BY 4.0" in text and "Apache-2.0" in text


def test_licensing_doc_records_the_decision():
    text = _read("docs/data-and-licensing.md").lower()
    assert "apache-2.0" in text and "cc by 4.0" in text and "cc0" in text
    assert "huggingface.co/datasets/tahoebio/tahoe-100m" in text


def test_no_document_still_says_licensing_is_unresolved():
    for rel in LICENSING_DOCS:
        text = _read(rel).lower()
        for phrase in STALE_PHRASES:
            assert phrase not in text, f"{rel}: {phrase}"


def test_both_manifests_declare_the_code_licence():
    # The code licence is one decision; both host manifests must carry it.
    for rel in (common.PLUGIN_MANIFEST_REL, common.CLAUDE_ADAPTER_REL):
        assert common.load_json(ROOT / rel).get("license") == "Apache-2.0", rel


def test_pyproject_license_matches_code_licence():
    assert f'license = "{common.CODE_LICENSE}"' in _read("pyproject.toml")


def test_license_paths_are_required_layout():
    assert "LICENSE" in common.REQUIRED_LAYOUT
    assert "LICENSE-CC-BY-4.0" in common.REQUIRED_LAYOUT
