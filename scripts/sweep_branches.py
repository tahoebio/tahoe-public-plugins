"""Report the leak/history scan for every remote branch.

    uv run python scripts/sweep_branches.py
    uv run python scripts/sweep_branches.py --root <repo> --refs origin/a origin/b

CI validates the commit under test on its own history. This sweep is the other
half of the design: a reporting-only pass over **every** remote branch, so the
pre-publication gate ("every remote branch's scan is green") has an artifact and
a dirty branch names the commit and the pusher who introduced it.

It never fails on a dirty branch: it prints a report and exits 0, so it can run
on a schedule without failing unrelated work. Only an operational error — git not
runnable, or a ref that cannot be read — exits non-zero.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import common  # noqa: E402

#: The remote-tracking ref namespace the sweep enumerates by default.
_REMOTE_PREFIX = "refs/remotes/"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True
    )


def _remote_refs(root: Path) -> list[tuple[str, str]]:
    """``(refname, tip sha)`` for every remote-tracking branch, HEAD excluded."""
    result = _git(
        root,
        "for-each-ref",
        "--format=%(refname) %(objectname)",
        "refs/remotes/",
    )
    if result.returncode:
        raise common.RepoError(
            f"git for-each-ref failed while listing branches ({result.returncode})"
        )
    refs: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        refname, _, tip = line.partition(" ")
        if not refname or refname.endswith("/HEAD"):
            continue
        refs.append((refname, tip))
    return refs


def _author(root: Path, commit: str) -> str:
    """The author of ``commit`` as ``Name <email>``, or ``""`` when unknown."""
    result = _git(root, "show", "-s", "--format=%an <%ae>", commit)
    return result.stdout.strip() if result.returncode == 0 else ""


def branch_reports(
    root: Path = common.REPO_ROOT, refs: list[str] | None = None
) -> list[dict]:
    """One report per ref: its tip, whether its own history is clean, and — when
    it is not — the offending commit and its author."""
    tips = dict(_remote_refs(root))
    targets = refs if refs is not None else list(tips)
    reports: list[dict] = []
    for ref in targets:
        findings = common.scan_history(root, ref=ref)
        commit = next((f["commit"] for f in findings if f["commit"]), "")
        tip = tips.get(ref) or _git(root, "rev-parse", ref).stdout.strip()
        reports.append(
            {
                "branch": (
                    ref[len(_REMOTE_PREFIX) :] if ref.startswith(_REMOTE_PREFIX) else ref
                ),
                "ref": ref,
                "tip": tip,
                "ok": not findings,
                "findings": len(findings),
                "commit": commit,
                "author": _author(root, commit) if commit else "",
            }
        )
    return reports


def _line(report: dict) -> str:
    status = "PASS" if report["ok"] else "FAIL"
    parts = [status, report["branch"], report["tip"][:12]]
    if not report["ok"]:
        parts.append(f"offending-commit={report['commit'][:12]}")
        parts.append(f"author={report['author'] or 'unknown'}")
        parts.append(f"findings={report['findings']}")
    return "  ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(common.REPO_ROOT))
    parser.add_argument(
        "--refs",
        nargs="*",
        default=None,
        help="refs to scan (default: every remote-tracking branch)",
    )
    args = parser.parse_args(argv)

    try:
        reports = branch_reports(Path(args.root), args.refs)
    except common.RepoError as exc:
        print(f"sweep failed: {exc}", file=sys.stderr)
        return 1

    print("branch leak sweep (per-ref history scan)")
    for report in reports:
        print("  " + _line(report))
    dirty = [report for report in reports if not report["ok"]]
    print(f"  {len(reports) - len(dirty)}/{len(reports)} branches clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
