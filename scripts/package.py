"""Build the release archive from approved tracked files only.

    uv run python scripts/package.py --out dist

The archive contains exactly the allowlisted plugin manifest files and nothing
else. A listed path that is missing, symlinked, escaping or generated is refused
rather than skipped. The built archive is scanned for internal residue and
secrets and is discarded if any are found. A SHA-256 checksum is written next to
the archive.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import common  # noqa: E402


def build_release(
    root: Path = common.REPO_ROOT, out_dir: Path | None = None
) -> tuple[Path, Path]:
    version = common.load_json(common.plugin_dir(root) / "plugin.json")["version"]
    members = common.collect_archive_members(root, common.tracked_files(root))
    destination = Path(out_dir) if out_dir is not None else root / "dist"
    archive = common.build_archive(
        root, members, destination / f"{common.PLUGIN_NAME}-{version}.zip"
    )

    findings = common.scan_archive(archive)
    if findings:
        archive.unlink(missing_ok=True)
        raise common.ResidueError(
            "the built archive contains forbidden residue or secrets:\n"
            + common.format_findings(findings)
        )
    return archive, common.write_checksum(archive)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(common.REPO_ROOT))
    parser.add_argument("--out", default=None, help="output directory (default: dist/)")
    args = parser.parse_args(argv)

    root = Path(args.root)
    out_dir = Path(args.out) if args.out else None
    try:
        archive, checksum = build_release(root, out_dir)
    except common.RepoError as exc:
        print(f"packaging failed: {exc}", file=sys.stderr)
        return 1

    print(f"archive:  {archive}")
    print(f"checksum: {checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
