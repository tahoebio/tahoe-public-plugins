"""The install prompt and the sign-in provider the docs promise.

Sign-in moves to Google or email in the browser, so the user-facing docs must
quote the one-line install prompt verbatim and must name that provider instead
of promising a GitHub account or consent screen.
"""

from scripts import common

INSTALL_DOC_REL = "docs/install.md"

#: The single-line install prompt quoted wherever the docs quote it.
NEW_INSTALL_PROMPT = (
    "Install the Tahoe plugin: add the marketplace tahoebio/tahoe-public-plugins, "
    "install the tara plugin, then connect to Tara. I'll sign in with Google or "
    "email in the browser."
)

#: Phrases that promise the old GitHub sign-in.
OLD_SIGNIN_PHRASES = ("github sign-in", "github account", "github consent")

#: User-facing docs that describe installing and signing in.
SIGNIN_DOCS = (
    "README.md",
    INSTALL_DOC_REL,
    "docs/compatibility.md",
    "docs/install-verification.md",
)


def _read(rel: str) -> str:
    return (common.REPO_ROOT / rel).read_text(encoding="utf-8")


def test_install_doc_quotes_the_new_prompt_verbatim():
    assert NEW_INSTALL_PROMPT in _read(INSTALL_DOC_REL)


def test_docs_name_google_or_email_sign_in():
    # The positive half of the guard: a doc that simply dropped its sign-in
    # sentence must not pass by silence.
    for rel in SIGNIN_DOCS:
        text = _read(rel).lower()
        assert "google" in text or "email" in text, f"{rel} names no sign-in provider"


def test_docs_do_not_promise_a_github_sign_in():
    for rel in SIGNIN_DOCS:
        text = _read(rel).lower()
        for phrase in OLD_SIGNIN_PHRASES:
            assert phrase not in text, f"{rel} still promises a GitHub sign-in: {phrase!r}"
