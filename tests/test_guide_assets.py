"""The public guide loads only reviewed, licensed brand files.

The guide is static HTML and CSS under ``docs/tara``. Its typefaces and the
Tahoe wordmark are binary files, so each one is pinned by digest in
``APPROVED_BINARY_ASSETS`` and named in the licence map. The guide must load
those files and no other resource.
"""

import hashlib
import re
from html.parser import HTMLParser
from pathlib import PurePosixPath

import pytest

from scripts import common

ROOT = common.REPO_ROOT

#: The files that state which licence covers which path.
LICENCE_MAPS = ("README.md", "NOTICE", "docs/data-and-licensing.md")

#: ``<link rel>`` values that make the browser fetch a resource.
LOADING_RELS = {"stylesheet", "icon", "preload", "modulepreload"}

PINNED_GUIDE_FILES = {
    common.GUIDE_WORDMARK_REL: common.APPROVED_BINARY_ASSETS[common.GUIDE_WORDMARK_REL],
    **common.GUIDE_FONT_DIGESTS,
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text()


def _in_guide(reference: str) -> str:
    """Resolve a guide-relative reference to a repository path."""
    return (PurePosixPath(common.GUIDE_DIR_REL) / reference).as_posix()


def _stylesheet() -> str:
    """The guide stylesheet without comments, so a disabled rule is not read."""
    return re.sub(r"/\*.*?\*/", "", _read(common.GUIDE_STYLESHEET_REL), flags=re.DOTALL)


def _stylesheet_urls(css: str) -> list[str]:
    return re.findall(r"""url\(\s*["']?([^"')\s]+)""", css)


def _licence_entries(rel: str) -> list[str]:
    """One string per licence-map entry: a table row, or a NOTICE paragraph."""
    text = _read(rel)
    if rel.endswith(".md"):
        return [line for line in text.splitlines() if line.startswith("|")]
    return [" ".join(block.split()) for block in text.split("\n\n")]


class _LoadedResources(HTMLParser):
    """Collect every reference a page makes the browser fetch on load."""

    def __init__(self) -> None:
        super().__init__()
        self.images: list[str] = []
        self.others: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "img":
            self.images.append(values.get("src") or "")
        elif tag == "link":
            rels = set((values.get("rel") or "").lower().split())
            if rels & LOADING_RELS:
                self.others.append(values.get("href") or "")
        elif tag in {"script", "iframe", "source", "video", "audio", "embed"}:
            if values.get("src"):
                self.others.append(values["src"] or "")


def _loaded(rel: str) -> _LoadedResources:
    parser = _LoadedResources()
    parser.feed(_read(rel))
    return parser


def test_stylesheet_loads_exactly_the_pinned_fonts():
    # A remote font, an unpinned file or a pinned file nothing loads all fail.
    urls = _stylesheet_urls(_stylesheet())
    assert urls, "the guide stylesheet declares no font files"
    assert {_in_guide(url) for url in urls} == set(common.GUIDE_FONT_DIGESTS)


def test_stylesheet_names_each_brand_family_it_loads():
    faces = re.findall(r"@font-face\s*\{[^}]*\}", _stylesheet())
    families = {re.search(r'font-family:\s*"([^"]+)"', face).group(1) for face in faces}
    assert families == {"Lato", "Inter Tight", "IBM Plex Mono"}


@pytest.mark.parametrize("page", common.GUIDE_PAGES)
def test_page_shows_the_pinned_wordmark_and_loads_only_local_files(page):
    loaded = _loaded(page)
    assert [_in_guide(src) for src in loaded.images] == [common.GUIDE_WORDMARK_REL]
    tracked = set(common.tracked_files(ROOT))
    for reference in loaded.images + loaded.others:
        assert "//" not in reference and not reference.startswith("/"), reference
        assert _in_guide(reference) in tracked, reference


@pytest.mark.parametrize(("rel", "digest"), sorted(PINNED_GUIDE_FILES.items()))
def test_pinned_guide_file_matches_its_reviewed_digest(rel, digest):
    assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("font", sorted(common.GUIDE_FONT_DIGESTS))
def test_each_font_file_ships_its_family_licence_text(font):
    family = PurePosixPath(font).name.split("-", 1)[0]
    licence = f"{common.GUIDE_FONTS_DIR_REL}/OFL-{family}.txt"
    assert licence in common.GUIDE_FONT_LICENSES
    text = _read(licence)
    assert text.startswith("Copyright")
    assert "SIL OPEN FONT LICENSE Version 1.1" in text


@pytest.mark.parametrize("rel", LICENCE_MAPS)
def test_licence_map_entry_for_the_typefaces_names_the_ofl(rel):
    # docs/** is CC BY 4.0; the typefaces are not. The entry that names their
    # path must itself carry their licence, not merely the same file.
    entries = [
        entry for entry in _licence_entries(rel) if f"{common.GUIDE_FONTS_DIR_REL}/" in entry
    ]
    assert entries, f"{rel} has no licence entry for the bundled typefaces"
    for entry in entries:
        assert "OFL-1.1" in entry or "SIL Open Font License 1.1" in entry, entry
        assert "CC-BY-4.0" not in entry and "CC BY 4.0" not in entry, entry


@pytest.mark.parametrize("rel", LICENCE_MAPS)
def test_licence_map_entry_for_the_wordmark_reserves_all_rights(rel):
    entries = [entry for entry in _licence_entries(rel) if common.GUIDE_WORDMARK_REL in entry]
    assert entries, f"{rel} has no licence entry for the guide wordmark"
    for entry in entries:
        assert "all rights reserved" in entry.lower(), entry
