"""Validate the public repository.

Checks the manifests and the MCP configuration against the vendored Agent
Plugins schemas, enforces the layout and version invariants, and scans the
working tree and the full git history for internal residue and secrets. Run
from the repository root:

    uv run python scripts/validate.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jsonschema import Draft202012Validator  # noqa: E402

from scripts import common  # noqa: E402


def _plugin_source(catalog: dict, rel: str, root: Path) -> str:
    """Return a catalog's declared source, checking the path is the plugin dir."""
    entries = catalog.get("plugins", [])
    if [entry.get("name") for entry in entries] != [common.PLUGIN_NAME]:
        raise common.RepoError(
            f"{rel}: expected exactly one entry named {common.PLUGIN_NAME!r}"
        )
    entry = entries[0]
    if "version" in entry:
        raise common.RepoError(f"{rel}: plugin version belongs in plugin.json only")

    path = entry.get("source")
    if not isinstance(path, str) or not path.startswith("./"):
        raise common.RepoError(f"{rel}: source path must be a ./ path")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise common.RepoError(f"{rel}: source path escapes the repository root")
    if resolved != common.plugin_dir(root).resolve():
        raise common.RepoError(f"{rel}: source path must point at the plugin directory")
    return path


def _validate_codex_catalog(catalog: dict, rel: str, root: Path) -> str:
    """Codex catalog shape: display name, install policy and category."""
    if catalog.get("name") != common.MARKETPLACE_NAME:
        raise common.RepoError(
            f"{rel}: marketplace name must be {common.MARKETPLACE_NAME!r}"
        )
    if catalog.get("interface", {}).get("displayName") != common.MARKETPLACE_DISPLAY_NAME:
        raise common.RepoError(
            f"{rel}: interface.displayName must be {common.MARKETPLACE_DISPLAY_NAME!r}"
        )
    source = _plugin_source(catalog, rel, root)

    entry = catalog["plugins"][0]
    policy = entry.get("policy", {})
    if policy.get("installation") not in common.INSTALLATION_POLICIES:
        raise common.RepoError(f"{rel}: policy.installation is missing or invalid")
    if not policy.get("authentication"):
        raise common.RepoError(f"{rel}: policy.authentication is required")
    if not entry.get("category"):
        raise common.RepoError(f"{rel}: category is required")
    return source


def _validate_claude_catalog(catalog: dict, rel: str, root: Path) -> str:
    """Claude catalog shape: an owner, then the same plugin identity/source."""
    if catalog.get("name") != common.MARKETPLACE_NAME:
        raise common.RepoError(
            f"{rel}: marketplace name must be {common.MARKETPLACE_NAME!r}"
        )
    if not catalog.get("owner", {}).get("name"):
        raise common.RepoError(f"{rel}: owner.name is required")
    return _plugin_source(catalog, rel, root)


def _validate_claude_adapter(root: Path) -> None:
    """Claude's native manifest, with the MCP server declared inline."""
    adapter = common.load_json(root / common.CLAUDE_ADAPTER_REL)
    if adapter.get("name") != common.PLUGIN_NAME:
        raise common.RepoError(
            f"{common.CLAUDE_ADAPTER_REL}: name must be {common.PLUGIN_NAME!r}"
        )

    servers = adapter.get("mcpServers", {})
    if list(servers) != [common.MCP_SERVER_NAME]:
        raise common.RepoError(
            f"{common.CLAUDE_ADAPTER_REL}: expected exactly one server named "
            f"{common.MCP_SERVER_NAME!r}"
        )
    server = servers[common.MCP_SERVER_NAME]
    if server.get("type") != "http":
        raise common.RepoError("the Claude adapter server must be type 'http'")
    if server.get("url") != common.MCP_ENDPOINT:
        raise common.RepoError(f"the Claude adapter url must be {common.MCP_ENDPOINT!r}")
    if "headers" in server or "env" in server:
        raise common.RepoError("the Claude adapter must not carry credentials")


def validate_manifests(root: Path = common.REPO_ROOT) -> None:
    manifest = common.load_json(root / common.PLUGIN_MANIFEST_REL)
    Draft202012Validator(common.load_schema("plugin")).validate(manifest)

    if manifest["name"] != common.PLUGIN_NAME:
        raise common.RepoError(f"plugin name must be {common.PLUGIN_NAME!r}")
    if "license" in manifest:
        raise common.RepoError(
            "plugin.json must not carry a license field until licensing is decided"
        )
    interface = manifest.get("extensions", {}).get("com.openai", {}).get("interface", {})
    for field in ("logo", "composerIcon"):
        if interface.get(field) != "./assets/tahoe-logo.png":
            raise common.RepoError(
                f"plugin.json interface.{field} must reference the reviewed Tahoe logo"
            )
    # No `skills` field: both hosts discover ``skills/`` by convention, and the
    # portable schema forbids unknown fields (`additionalProperties: false`).

    codex = common.load_json(root / common.CODEX_CATALOG_REL)
    claude = common.load_json(root / common.CLAUDE_CATALOG_REL)
    codex_source = _validate_codex_catalog(codex, common.CODEX_CATALOG_REL, root)
    claude_source = _validate_claude_catalog(claude, common.CLAUDE_CATALOG_REL, root)

    # The catalogs have different shapes; they must still agree on the
    # marketplace identity and on which plugin directory they resolve.
    if codex.get("name") != claude.get("name"):
        raise common.RepoError("catalogs must agree on the marketplace name")
    if codex_source != claude_source:
        raise common.RepoError("catalogs must resolve the same plugin directory")

    _validate_claude_adapter(root)


def validate_layout(root: Path = common.REPO_ROOT) -> None:
    missing = [rel for rel in common.REQUIRED_LAYOUT if not (root / rel).exists()]
    if missing:
        raise common.RepoError("missing layout paths: " + ", ".join(missing))


def validate_mcp_config(root: Path = common.REPO_ROOT) -> None:
    config = common.load_json(root / common.MCP_CONFIG_REL)
    Draft202012Validator(common.load_schema("mcp")).validate(config)

    servers = config["mcpServers"]
    if list(servers) != [common.MCP_SERVER_NAME]:
        raise common.RepoError(
            f"{common.MCP_CONFIG_REL}: expected exactly one server named "
            f"{common.MCP_SERVER_NAME!r}"
        )
    server = servers[common.MCP_SERVER_NAME]
    if server.get("type") != "streamable-http":
        raise common.RepoError("mcp server must be streamable-http")
    if server.get("url") != common.MCP_ENDPOINT:
        raise common.RepoError(f"mcp server url must be {common.MCP_ENDPOINT!r}")
    if "headers" in server or "env" in server:
        raise common.RepoError("mcp.json must not carry credentials")


def validate_min_server_version(root: Path = common.REPO_ROOT) -> None:
    """The minimum public server version each manifest declares.

    The floor must be a semver string and identical in both host manifests, so
    the two hosts never carry a different floor for the same server.
    """
    declared: list[tuple[str, str | None]] = []
    for rel in (common.PLUGIN_MANIFEST_REL, common.CLAUDE_ADAPTER_REL):
        value = common.min_server_version(common.load_json(root / rel))
        if not isinstance(value, str) or not common.SEMVER.match(value):
            raise common.RepoError(
                f"{rel}: extensions[{common.TAHOE_EXTENSION_NAMESPACE!r}]"
                f"[{common.MIN_SERVER_VERSION_FIELD!r}] must be a semver string"
            )
        declared.append((rel, value))
    (portable_rel, portable), (claude_rel, claude) = declared
    if portable != claude:
        raise common.RepoError(
            "the two manifests declare different minimum server versions: "
            f"{portable_rel} {portable!r} vs {claude_rel} {claude!r}"
        )


def validate_versions(root: Path = common.REPO_ROOT) -> None:
    version = common.load_json(root / common.PLUGIN_MANIFEST_REL)["version"]
    if not common.SEMVER.match(version):
        raise common.RepoError(f"plugin version {version!r} is not semver")
    if common.pyproject_version(root) != version:
        raise common.RepoError("pyproject.toml version must match plugin.json")

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if version not in changelog:
        raise common.RepoError("CHANGELOG.md must record the plugin version")


def validate_residue(
    root: Path = common.REPO_ROOT, *, ref: str | None = None, all_refs: bool = False
) -> None:
    """Scan the working tree and the ref under test for residue and secrets.

    The history scan covers ``ref`` (default ``HEAD``) by default, so a scan is a
    function of this ref and cannot be failed by another branch or tag. When
    ``ref`` is an annotated tag, the tag object's own message is scanned too.
    ``all_refs=True`` sweeps every ref and every annotated tag — a
    developer/pre-publication check, never the CI default.

    Fails rather than reporting clean when the history cannot be read in full.
    """
    common.require_full_history(root)
    findings = common.scan_repo(root=root) + common.scan_history(
        root, ref=ref, all_refs=all_refs
    )
    if findings:
        raise common.ResidueError(
            "forbidden residue or secrets found:\n" + common.format_findings(findings)
        )


def _skill_texts(root: Path) -> dict[str, str]:
    """The skill's files, as ``relative path -> text``."""
    return {
        rel: (root / rel).read_text(encoding="utf-8") for rel in common.SKILL_FILES
    }


def validate_tool_contract(root: Path = common.REPO_ROOT) -> None:
    """Fail when the tool-contract table drifts from the pinned public tool list."""
    known = common.known_tools(root)
    if known != common.PINNED_PUBLIC_TOOLS:
        raise common.RepoError(
            "the tool contract drifted from the pinned public tool list "
            f"(revision {common.PINNED_PUBLIC_TOOLS_REVISION}): missing "
            f"{sorted(common.PINNED_PUBLIC_TOOLS - known)}, unexpected "
            f"{sorted(known - common.PINNED_PUBLIC_TOOLS)}"
        )


def validate_skill(root: Path = common.REPO_ROOT) -> None:
    """Enforce the skill payload's shape, budgets and vocabulary.

    Checks the frontmatter, the tier byte budgets, that every relative link
    resolves inside the skill directory, that every tool the text names is on the
    public tool contract, and that no locator, volume path or internal cell code
    appears in the shipped text.
    """
    if not (root / common.SKILL_MD_REL).is_file():
        raise common.RepoError(f"missing skill file: {common.SKILL_MD_REL}")

    texts = _skill_texts(root)
    fields = common.parse_frontmatter(texts[common.SKILL_MD_REL])
    if fields.get("name") != common.PLUGIN_NAME:
        raise common.RepoError(
            f"{common.SKILL_MD_REL}: frontmatter name must be {common.PLUGIN_NAME!r}"
        )
    description = fields.get("description", "")
    if not 1 <= len(description) <= common.SKILL_DESCRIPTION_MAX_CHARS:
        raise common.RepoError(
            f"{common.SKILL_MD_REL}: description must be 1 to "
            f"{common.SKILL_DESCRIPTION_MAX_CHARS} characters"
        )

    body_bytes = len(texts[common.SKILL_MD_REL].encode("utf-8"))
    if body_bytes > common.SKILL_BODY_MAX_BYTES:
        raise common.RepoError(
            f"{common.SKILL_MD_REL}: {body_bytes} bytes exceeds the "
            f"{common.SKILL_BODY_MAX_BYTES}-byte budget"
        )

    for rel in common.REFERENCE_RELS:
        if rel not in texts:
            raise common.RepoError(f"missing skill reference: {rel}")
    references_bytes = sum(
        len(texts[rel].encode("utf-8")) for rel in common.REFERENCE_RELS
    )
    if references_bytes > common.REFERENCES_MAX_BYTES:
        raise common.RepoError(
            f"skill references total {references_bytes} bytes, over the "
            f"{common.REFERENCES_MAX_BYTES}-byte budget"
        )

    skill_dir = (root / common.SKILL_DIR_REL).resolve()
    known = common.known_tools(root)
    planned = common.planned_tools(root)
    if known & planned:
        raise common.RepoError(
            "the tool contract lists a tool as both live and not-yet-served: "
            + ", ".join(sorted(known & planned))
        )
    for rel, text in texts.items():
        for target in common.relative_links(text):
            resolved = (root / rel).parent.joinpath(target).resolve()
            if not resolved.is_relative_to(skill_dir) or not resolved.is_file():
                raise common.RepoError(
                    f"{rel}: link does not resolve inside the skill dir: {target}"
                )
        for name in common.tool_shaped_mentions(text):
            if name in known:
                continue
            if name in planned and common.names_coming_soon(text, name):
                continue
            raise common.RepoError(
                f"{rel}: names a tool that is neither on the public tool contract "
                f"nor marked as not yet served: {name}"
            )
        if common.locator_tokens(text):
            raise common.RepoError(
                f"{rel}: contains a three-part locator: "
                f"{common.locator_tokens(text)[0]}"
            )
        if common.cell_code_tokens(text):
            raise common.RepoError(
                f"{rel}: contains an internal cell code: "
                f"{common.cell_code_tokens(text)[0]}"
            )


def validate_all(
    root: Path = common.REPO_ROOT, *, ref: str | None = None, all_refs: bool = False
) -> None:
    validate_manifests(root)
    validate_layout(root)
    validate_mcp_config(root)
    validate_min_server_version(root)
    validate_versions(root)
    validate_tool_contract(root)
    validate_skill(root)
    validate_residue(root, ref=ref, all_refs=all_refs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root", nargs="?", default=str(common.REPO_ROOT), help="repository root"
    )
    parser.add_argument(
        "--ref",
        default=None,
        help="the ref under test to scan (default: HEAD). On a tag push, pass the "
        "tag ref so the tag object's own message is scanned",
    )
    parser.add_argument(
        "--all-refs",
        action="store_true",
        help="scan every ref's history and every annotated tag (developer/"
        "pre-publication sweep; CI scans the ref under test only)",
    )
    args = parser.parse_args(argv)
    try:
        validate_all(Path(args.root), ref=args.ref, all_refs=args.all_refs)
    except common.RepoError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
