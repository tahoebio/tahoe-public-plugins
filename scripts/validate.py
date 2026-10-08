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


def _validate_catalog(catalog: dict, rel: str, root: Path) -> None:
    if catalog.get("name") != common.MARKETPLACE_NAME:
        raise common.RepoError(f"{rel}: marketplace name must be {common.MARKETPLACE_NAME!r}")
    if catalog.get("interface", {}).get("displayName") != common.MARKETPLACE_DISPLAY_NAME:
        raise common.RepoError(
            f"{rel}: interface.displayName must be {common.MARKETPLACE_DISPLAY_NAME!r}"
        )

    entries = catalog.get("plugins", [])
    if [entry.get("name") for entry in entries] != [common.PLUGIN_NAME]:
        raise common.RepoError(
            f"{rel}: expected exactly one entry named {common.PLUGIN_NAME!r}"
        )

    entry = entries[0]
    policy = entry.get("policy", {})
    if policy.get("installation") not in common.INSTALLATION_POLICIES:
        raise common.RepoError(f"{rel}: policy.installation is missing or invalid")
    if not policy.get("authentication"):
        raise common.RepoError(f"{rel}: policy.authentication is required")
    if not entry.get("category"):
        raise common.RepoError(f"{rel}: category is required")
    if "version" in entry:
        raise common.RepoError(f"{rel}: plugin version belongs in plugin.json only")

    source = entry.get("source")
    path = source["path"] if isinstance(source, dict) else source
    if not isinstance(path, str) or not path.startswith("./"):
        raise common.RepoError(f"{rel}: source path must be a ./ path")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise common.RepoError(f"{rel}: source path escapes the repository root")
    if resolved != common.plugin_dir(root).resolve():
        raise common.RepoError(f"{rel}: source path must point at the plugin directory")


def validate_manifests(root: Path = common.REPO_ROOT) -> None:
    manifest = common.load_json(common.plugin_dir(root) / "plugin.json")
    Draft202012Validator(common.load_schema("plugin")).validate(manifest)

    if manifest["name"] != common.PLUGIN_NAME:
        raise common.RepoError(f"plugin name must be {common.PLUGIN_NAME!r}")
    if "license" in manifest:
        raise common.RepoError(
            "plugin.json must not carry a license field until licensing is decided"
        )

    canonical_rel = common.MARKETPLACE_PATHS[0]
    canonical = common.load_json(root / canonical_rel)
    legacy = common.load_json(root / common.MARKETPLACE_PATHS[1])
    if canonical != legacy:
        raise common.RepoError("marketplace catalogs must be identical")

    _validate_catalog(canonical, canonical_rel, root)


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
    version = common.load_json(common.plugin_dir(root) / "plugin.json")["version"]
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
