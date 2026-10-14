"""The install prompt, the sign-in provider and the restart step the docs promise.

The repository is public and sign-in is Google, so the user-facing docs must
quote the install prompt verbatim, name Google, and never promise a GitHub
sign-in, a private/unpublished status, or an email sign-up a new user cannot use.
"""

from scripts import common

INSTALL_DOC_REL = "docs/install.md"

#: The single-line install prompt quoted wherever the docs quote it.
NEW_INSTALL_PROMPT = (
    "Install the Tahoe plugin: add the marketplace tahoebio/tahoe-public-plugins, "
    "install the tara plugin, then connect to Tara. I'll sign in with Google in "
    "the browser."
)

#: The Codex sign-in command, composed from the server-name constant.
CODEX_LOGIN = f"codex mcp login {common.MCP_SERVER_NAME}"

#: Phrases that promise the old GitHub sign-in.
OLD_SIGNIN_PHRASES = ("github sign-in", "github account", "github consent")

#: Phrases that promise a sign-in method a new user cannot use.
OLD_EMAIL_PHRASES = ("google or email", "email sign-up", "sign up with email")

#: Phrases that claim the repository is not public.
NOT_PUBLIC_PHRASES = (
    "private preview",
    "not published",
    "publication blocker",
    "not a supported release",
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


def _flatten(rel: str) -> str:
    """The doc's text, lowercased with whitespace collapsed.

    Collapsing whitespace keeps a phrase match from missing a line-wrapped
    occurrence (for example a phrase split across a Markdown blockquote).
    """
    return " ".join((common.REPO_ROOT / rel).read_text(encoding="utf-8").lower().split())


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


def test_readme_does_not_claim_the_repo_is_private():
    _assert_phrases_absent("README.md", NOT_PUBLIC_PHRASES, "still claims it is not public")


def test_docs_state_the_restart_and_codex_login_steps():
    for rel in INSTALL_STEP_DOCS:
        text = _flatten(rel)
        assert "restart" in text, f"{rel} omits the restart step"
        assert CODEX_LOGIN in text, f"{rel} omits the Codex sign-in step"


def test_install_doc_tells_older_connections_to_re_add():
    text = _flatten(INSTALL_DOC_REL)
    assert "re-add" in text, "install.md omits the remove/re-add note"
    assert "2026-10-14" in text, "install.md omits the pre-Google connection date"
