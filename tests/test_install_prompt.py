"""Install copy agrees on client-owned login and preserves credential protections."""

import functools
from pathlib import Path

from scripts import common

INSTALL_DOC_REL = "docs/install.md"

CURRENT_INSTALL_PROMPT = "Use curl to read https://tara.tahoebio.io/install.md and perform the setup to install Tara"

#: Docs that quote the install prompt, so its copies cannot drift apart.
PROMPT_DOCS = ("README.md",)

#: The Codex sign-in and remove commands, composed from the server-name constant.
CODEX_LOGIN = f"codex mcp login {common.MCP_SERVER_NAME}"
CODEX_REMOVE = f"codex mcp remove {common.MCP_SERVER_NAME}"

#: Phrases that promise a GitHub sign-in. Deliberately not the bare word
#: "github", so a legitimate repository link is not rejected.
OLD_SIGNIN_PHRASES = (
    "github sign-in",
    "github account",
    "github consent",
    "github login",
    "github oauth",
    "sign in with github",
)

#: Phrases that frame the project as pre-publication. "publication" is the shared
#: stem of every such claim, so one entry covers them all.
NOT_PUBLIC_PHRASES = (
    "private preview",
    "not published",
    "not a supported release",
    "publication",
)

#: User-facing docs that describe installing and signing in.
SIGNIN_DOCS = (
    "README.md",
    INSTALL_DOC_REL,
    "docs/compatibility.md",
    "docs/install-verification.md",
)

#: Suffixes of shipped, reader-facing text.
SHIPPED_SUFFIXES = frozenset({".md", ".py", ".json", ".yml", ".yaml"})


@functools.lru_cache(maxsize=None)
def _flatten(rel: str) -> str:
    """The file's text, lowercased, with ``>`` characters and whitespace removed.

    Dropping ``>`` and collapsing whitespace keeps a phrase match from missing an
    occurrence wrapped across a Markdown blockquote.
    """
    text = (common.REPO_ROOT / rel).read_text(encoding="utf-8").lower()
    return " ".join(text.replace(">", " ").split())


def _shipped_text_files() -> tuple[str, ...]:
    """Tracked files that ship as reader-facing text.

    The changelog records past state and is correctly left alone; the tests are
    not shipped text.
    """
    return tuple(
        rel
        for rel in common.tracked_files()
        if rel != "CHANGELOG.md"
        and not rel.startswith("tests/")
        and Path(rel).suffix in SHIPPED_SUFFIXES
    )


def _assert_phrases_absent(rel: str, phrases: tuple[str, ...], claim: str) -> None:
    text = _flatten(rel)
    for phrase in phrases:
        assert phrase not in text, f"{rel} {claim}: {phrase!r}"


def test_install_prompt_is_quoted_verbatim_in_every_doc():
    for rel in PROMPT_DOCS:
        lines = (common.REPO_ROOT / rel).read_text(encoding="utf-8").splitlines()
        assert f"> {CURRENT_INSTALL_PROMPT}" in lines, f"{rel} quotes a different install prompt"


def test_install_docs_defer_to_the_served_guide():
    for rel in ("README.md", INSTALL_DOC_REL):
        text = _flatten(rel)
        assert "https://tara.tahoebio.io/install.md" in text
        for old in ("then stop", "installs and stops", "do not try to sign in"):
            assert old not in text
        # Installation commands belong to the served guide, not a second procedure.
        assert "plugin marketplace add" not in text
        assert "mcp add --" not in text


def test_docs_name_google_sign_in():
    for rel in SIGNIN_DOCS:
        assert "google" in _flatten(rel), f"{rel} does not name Google sign-in"


def test_docs_do_not_promise_a_github_sign_in():
    for rel in SIGNIN_DOCS:
        _assert_phrases_absent(rel, OLD_SIGNIN_PHRASES, "still promises a GitHub sign-in")


def test_docs_allow_verified_email_sign_in():
    for rel in SIGNIN_DOCS:
        assert "verified email address" in _flatten(rel), (
            f"{rel} does not name verified email sign-in"
        )


def test_public_text_does_not_claim_the_repo_is_not_public():
    for rel in _shipped_text_files():
        _assert_phrases_absent(rel, NOT_PUBLIC_PHRASES, "still claims it is not public")


def test_verification_preserves_per_client_handoff_and_same_connection_witness():
    text = _flatten("docs/install-verification.md")
    assert CODEX_LOGIN in text
    assert "new codex session" in text
    assert "no restart needed" in text and "`/mcp`" in text
    assert "through that same client connection" in text
    assert "`list_releases`" in text
    for rel in SIGNIN_DOCS:
        assert "restart claude code" not in _flatten(rel)


def test_install_doc_tells_older_connections_to_re_add():
    text = _flatten(INSTALL_DOC_REL)
    assert "re-add" in text, "install.md omits the remove/re-add note"
    assert "2026-10-14" in text, "install.md omits the pre-Google connection date"
    assert CODEX_REMOVE in text, "install.md omits the Codex remove command"
    assert "codex plugin remove tara@tahoe-public" in text
    assert "do not add a duplicate direct server entry" in text


def test_security_policy_names_a_private_reporting_route():
    text = _flatten("SECURITY.md")
    assert "report a vulnerability" in text, "SECURITY.md names no GitHub route"
    assert "tara@tahoebio.ai" in text, "SECURITY.md names no email fallback"
