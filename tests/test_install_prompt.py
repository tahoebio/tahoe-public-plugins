"""The install prompt, the sign-in provider and the restart step the docs promise.

The repository is public and sign-in is Google, so the user-facing docs must
quote the install prompt verbatim, name Google, and never promise a GitHub
sign-in, a private/unpublished status, or an email sign-up a new user cannot use.
"""

import functools
from pathlib import Path

from scripts import common

INSTALL_DOC_REL = "docs/install.md"

#: The single-line install prompt quoted wherever the docs quote it.
NEW_INSTALL_PROMPT = (
    "Install the Tahoe plugin: add the marketplace tahoebio/tahoe-public-plugins, "
    "install the tara plugin, then connect to Tara. I'll sign in with Google in "
    "the browser."
)

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

#: Phrases that promise a sign-in method a new user cannot use.
OLD_EMAIL_PHRASES = ("google or email", "email sign-up", "sign up with email")

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

#: Docs that carry the install steps; compatibility.md lists requirements only.
INSTALL_STEP_DOCS = tuple(rel for rel in SIGNIN_DOCS if rel != "docs/compatibility.md")

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


def test_install_doc_quotes_the_new_prompt_verbatim():
    assert NEW_INSTALL_PROMPT in (common.REPO_ROOT / INSTALL_DOC_REL).read_text(
        encoding="utf-8"
    )


def test_docs_name_google_sign_in():
    for rel in SIGNIN_DOCS:
        assert "google" in _flatten(rel), f"{rel} does not name Google sign-in"


def test_docs_do_not_promise_a_github_sign_in():
    for rel in SIGNIN_DOCS:
        _assert_phrases_absent(rel, OLD_SIGNIN_PHRASES, "still promises a GitHub sign-in")


def test_docs_do_not_promise_email_sign_up():
    for rel in SIGNIN_DOCS:
        _assert_phrases_absent(rel, OLD_EMAIL_PHRASES, "still promises email sign-up")


def test_public_text_does_not_claim_the_repo_is_not_public():
    for rel in _shipped_text_files():
        _assert_phrases_absent(rel, NOT_PUBLIC_PHRASES, "still claims it is not public")


def test_docs_state_the_restart_and_codex_login_steps():
    for rel in INSTALL_STEP_DOCS:
        text = _flatten(rel)
        assert "restart" in text, f"{rel} omits the restart step"
        assert CODEX_LOGIN in text, f"{rel} omits the Codex sign-in step"


def test_install_doc_tells_older_connections_to_re_add():
    text = _flatten(INSTALL_DOC_REL)
    assert "re-add" in text, "install.md omits the remove/re-add note"
    assert "2026-10-14" in text, "install.md omits the pre-Google connection date"
    assert CODEX_REMOVE in text, "install.md omits the Codex remove command"


def test_security_policy_names_a_private_reporting_route():
    text = _flatten("SECURITY.md")
    assert "report a vulnerability" in text, "SECURITY.md names no GitHub route"
    assert "tara@tahoebio.ai" in text, "SECURITY.md names no email fallback"
