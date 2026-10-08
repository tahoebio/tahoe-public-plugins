"""Validate the public repository.

Checks the manifests and the MCP configuration against the vendored Agent
Plugins schemas, enforces the layout and version invariants, and scans the
working tree and the full git history for internal residue and secrets. Run
from the repository root:

    uv run python scripts/validate.py
"""

from __future__ import annotations

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
    if "skills" in manifest:
        raise common.RepoError("the thin plugin must not declare a skills payload")

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


def validate_versions(root: Path = common.REPO_ROOT) -> None:
    version = common.load_json(root / common.PLUGIN_MANIFEST_REL)["version"]
    if not common.SEMVER.match(version):
        raise common.RepoError(f"plugin version {version!r} is not semver")
    if common.pyproject_version(root) != version:
        raise common.RepoError("pyproject.toml version must match plugin.json")

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if version not in changelog:
        raise common.RepoError("CHANGELOG.md must record the plugin version")


def validate_residue(root: Path = common.REPO_ROOT) -> None:
    """Scan the working tree and the full git history for residue and secrets.

    Fails rather than reporting clean when the history cannot be read in full.
    """
    common.require_full_history(root)
    findings = common.scan_repo(root=root) + common.scan_history(root=root)
    if findings:
        raise common.ResidueError(
            "forbidden residue or secrets found:\n" + common.format_findings(findings)
        )


def validate_all(root: Path = common.REPO_ROOT) -> None:
    validate_manifests(root)
    validate_layout(root)
    validate_mcp_config(root)
    validate_versions(root)
    validate_residue(root)


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]) if argv else common.REPO_ROOT
    try:
        validate_all(root)
    except common.RepoError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
