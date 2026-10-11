"""Report the leak/history scan for every remote branch and every annotated tag.

    uv run python scripts/sweep_branches.py
    uv run python scripts/sweep_branches.py --root <repo> --refs origin/a origin/b

CI validates the commit under test on its own history. This sweep is the other
half of the design: a reporting-only pass over **every** remote branch **and
every annotated tag**, so the pre-publication gate ("every remote branch's scan
is green") has an artifact and a dirty ref names the commit that introduced the
offence and its author. Annotated tags are included because a tag object carries
its own message, which no commit walk reads.

It never fails on a dirty ref: it prints a report and exits 0, so it can run on a
schedule without failing unrelated work. It DOES fail (non-zero) when it cannot
do its job — git not runnable, a ref or tag object that cannot be read, or no
refs found at all (reporting "0/0 clean" would be a silent pass).
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


def _author(root: Path, obj: str) -> str:
    """The author of ``obj`` as ``Name <email>``, or ``""`` when unknown.

    A tag object has a tagger, not an author; read it from the tag object so a
    tag-message finding names the person who wrote it.
    """
    if not obj:
        return ""
    kind = _git(root, "cat-file", "-t", obj).stdout.strip()
    if kind == "tag":
        for line in _git(root, "cat-file", "-p", obj).stdout.splitlines():
            if line.startswith("tagger "):
                return line[len("tagger ") :].rsplit(">", 1)[0] + ">"
        return ""
    result = _git(root, "show", "-s", "--format=%an <%ae>", obj)
    return result.stdout.strip() if result.returncode == 0 else ""


def _report(root: Path, ref: str, tip: str, kind: str) -> dict:
    """One ref's report: its tip, whether its own history is clean, and — when it
    is not — the offending commit and its author (or the tagger)."""
    findings = common.scan_history(root, ref=ref)
    commit = next((f["commit"] for f in findings if f["commit"]), "")
    author = next((f["author"] for f in findings if f["author"]), "")
    if commit and not author:
        author = _author(root, commit)
    if kind == "tag":
        name = ref[len("refs/tags/") :] if ref.startswith("refs/tags/") else ref
        label = f"tag/{name}"
    else:
        label = ref[len(_REMOTE_PREFIX) :] if ref.startswith(_REMOTE_PREFIX) else ref
    return {
        "branch": label,
        "kind": kind,
        "ref": ref,
        "tip": tip,
        "ok": not findings,
        "findings": len(findings),
        "commit": commit,
        "author": author,
    }


def branch_reports(
    root: Path = common.REPO_ROOT, refs: list[str] | None = None
) -> list[dict]:
    """One report per ref: every remote branch, and every tag.

    Every tag is enumerated — annotated and lightweight — and each is scanned on
    its OWN ref, so a tag that is the sole ref to a dirty commit is caught and no
    tag's verdict depends on a sibling tag. An annotated tag's message is scanned
    with its own ref (a tag object is not a commit).
    """
    tips = dict(_remote_refs(root))
    targets = refs if refs is not None else list(tips)
    reports = [
        _report(
            root, ref, tips.get(ref) or _git(root, "rev-parse", ref).stdout.strip(), "branch"
        )
        for ref in targets
    ]
    reports.extend(
        _report(root, refname, sha, "tag") for refname, sha in common.all_tags(root)
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

    if not reports:
        print(
            "sweep failed: no remote branches found to scan (did the fetch run? "
            "the sweep reports nothing rather than passing silently)",
            file=sys.stderr,
        )
        return 1

    print("branch leak sweep (per-ref history scan)")
    for report in reports:
        print("  " + _line(report))
    dirty = [report for report in reports if not report["ok"]]
    print(f"  {len(reports) - len(dirty)}/{len(reports)} refs clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
