"""The public sign-in wording: Google, no GitHub, no preview.

The repository is public and the server signs callers in with **Google**
(Cognito), so the shipped skill text and the docs this change owns must name
Google and must never promise a GitHub sign-in or a private/limited "preview".
`README.md` and `SECURITY.md` are owned by the install-prompt doc change and are
covered there, not here.
"""

from scripts import common

#: The shipped text and docs this change owns.
WORDING_FILES = (
    "docs/compatibility.md",
    "docs/install.md",
    "docs/install-verification.md",
    "plugins/tara/skills/tara/SKILL.md",
    common.ROUTING_REL,
    "evals/tara/frozen-expected-0.3.x.md",
)

#: The docs that carry install steps (they also state the restart step).
INSTALL_STEP_DOCS = ("docs/install.md", "docs/install-verification.md")

#: Phrases that promise the old GitHub sign-in.
GITHUB_SIGNIN_PHRASES = (
    "github sign-in",
    "github sign in",
    "github account",
    "github consent",
    "github during",
    "sign in with github",
)

#: Phrases that claim a private or limited preview.
PREVIEW_PHRASES = ("preview",)

#: The Codex sign-in command, composed from the server-name constant.
CODEX_LOGIN = f"codex mcp login {common.MCP_SERVER_NAME}"


def _flatten(rel: str) -> str:
    """The file's text, lowercased with whitespace collapsed.

    Collapsing whitespace keeps a phrase match from missing a line-wrapped
    occurrence (for example a phrase split across a Markdown bullet).
    """
    return " ".join(
        (common.REPO_ROOT / rel).read_text(encoding="utf-8").lower().split()
    )


def test_shipped_text_promises_no_github_sign_in():
    for rel in WORDING_FILES:
        text = _flatten(rel)
        for phrase in GITHUB_SIGNIN_PHRASES:
            assert phrase not in text, f"{rel} still promises a GitHub sign-in: {phrase!r}"


def test_changelog_entry_promises_no_github_sign_in():
    # The changelog records past wording; only the sign-in phrases are checked
    # (a bare "GitHub" is legitimate in a tooling note).
    text = _flatten("CHANGELOG.md")
    for phrase in GITHUB_SIGNIN_PHRASES:
        assert phrase not in text, f"CHANGELOG.md still promises a GitHub sign-in: {phrase!r}"


def test_shipped_text_does_not_claim_a_preview():
    for rel in WORDING_FILES:
        assert "preview" not in _flatten(rel), f"{rel} still claims a preview"


def test_sign_in_docs_name_google():
    for rel in ("docs/compatibility.md", *INSTALL_STEP_DOCS):
        assert "google" in _flatten(rel), f"{rel} does not name Google sign-in"


def test_install_docs_state_the_restart_and_codex_login_steps():
    for rel in INSTALL_STEP_DOCS:
        text = _flatten(rel)
        assert "restart" in text, f"{rel} omits the restart step"
        assert CODEX_LOGIN in text, f"{rel} omits the Codex sign-in step"


def test_skill_identity_guidance_names_google():
    assert "google" in _flatten(common.ROUTING_REL)
