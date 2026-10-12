"""Human-facing manifest text: honest, identical across hosts, no dataset names."""

import re

import pytest

from helpers import j
from scripts import common

FORBIDDEN = [
    j("Tahoe-", "100M"),
    j("Tahoe", "100M"),
    j("Cas", "pian"),
    j("Mam", "moth"),
    j("Yose", "mite"),
    j("Dep", "Map"),
    j("PR", "ISM"),
    j("NCI", "60"),
    j("LI", "NCS"),
    j("Data", "bricks"),
    j("inter", "nal"),
    "target discovery",
    "target deconvolution",
    "biomarker discovery",
    "responder stratification",
    "pharmacogenomic sensitivity",
    "dependencies",
    "viability",
    "IC50",
    "AUC",
]

CAPABILITIES = [
    "annotated mechanism classes",
    "baseline expression or driver-gene status",
    "genotype- or lineage-defined groups of cell lines",
    "relative depletion and cell-cycle effects per cell line across three doses",
]

DEFAULT_PROMPTS = [
    "Which MEK and RAF inhibitors are in Tahoe's data?",
    "In Tahoe's data, is Pitavastatin's stronger suppression of YAP signaling "
    "than Pravastatin driven by greater on-target activity?",
    "Does binimetinib up- or down-regulate KRAS signaling in Tahoe's data?",
]


def _portable() -> dict:
    return common.load_json(common.plugin_dir() / "plugin.json")


def _claude() -> dict:
    return common.load_json(common.REPO_ROOT / common.CLAUDE_ADAPTER_REL)


def _interface() -> dict:
    return _portable()["extensions"]["com.openai"]["interface"]


def _human_text() -> list[str]:
    portable, claude, interface = _portable(), _claude(), _interface()
    texts = [portable["description"], claude["description"], *portable["keywords"]]
    texts += [v for v in interface.values() if isinstance(v, str)]
    texts += interface["defaultPrompt"]
    return texts


def test_descriptions_are_identical_across_manifests():
    portable, claude = _portable(), _claude()
    assert portable["description"] == claude["description"]
    assert _interface()["longDescription"] == portable["description"]


@pytest.mark.parametrize("word", FORBIDDEN)
def test_no_forbidden_term_in_manifest_text(word):
    pattern = re.compile(re.escape(word), re.IGNORECASE)
    assert [t for t in _human_text() if pattern.search(t)] == []


def test_interface_fields():
    interface = _interface()
    assert interface["displayName"] == "Tara"
    assert interface["shortDescription"] == (
        "Analyze Tahoe's frontier-scale perturbation data."
    )
    assert interface["developerName"] == "Tahoe Bio"
    assert interface["category"] == "Research"
    assert interface["capabilities"] == ["Read"]
    assert interface["websiteURL"] == "https://tara.tahoebio.io/"
    assert interface["brandColor"] == "#082846"


def test_no_logo_fields_until_an_asset_exists():
    interface = _interface()
    assets = common.plugin_dir() / "assets"
    has_logo = any(p.suffix in {".png", ".svg"} for p in assets.glob("*"))
    if not has_logo:
        assert "logo" not in interface and "composerIcon" not in interface


def test_default_prompts_are_exactly_the_verified_three():
    assert _interface()["defaultPrompt"] == DEFAULT_PROMPTS


def test_interface_category_matches_marketplace():
    catalog = common.load_json(common.REPO_ROOT / common.CODEX_CATALOG_REL)
    assert _interface()["category"] == catalog["plugins"][0]["category"]


def test_keywords_drop_dataset_name():
    assert _portable()["keywords"] == [
        "single-cell",
        "perturbation",
        "drug-discovery",
        "gene-expression",
        "pathways",
        "mcp",
    ]



@pytest.mark.parametrize("phrase", CAPABILITIES)
def test_description_states_each_audited_capability(phrase):
    assert phrase in _portable()["description"]
