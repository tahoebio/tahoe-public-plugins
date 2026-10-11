# Releasing

> Validation, packaging and the leak scans are in place. Publication itself is
> still blocked (see below).

## Validation

`scripts/validate.py` checks the manifests and the MCP configuration against
the vendored Agent Plugins schemas, enforces layout and version invariants, and
scans both the working tree and the git history for internal residue and
secrets. CI checks out the full history so the scan covers every commit **of the
ref under test**: the history scan is a function of the commit, so one stale
branch cannot fail an unrelated branch or `main`. A developer can widen the scan
to every ref with `uv run python scripts/validate.py --all-refs`.

## Branch leak sweep (pre-publication gate)

`scripts/sweep_branches.py` runs the same per-ref scan once for **every** remote
branch and prints a report (`branch · tip · offending commit · author · pass/fail`).
It reports and exits 0 — a dirty branch never fails unrelated work. It runs on
`workflow_dispatch` and a weekly schedule (`.github/workflows/sweep.yml`), and
locally:

```sh
git fetch --prune origin "+refs/heads/*:refs/remotes/origin/*"
uv run python scripts/sweep_branches.py
```

**Gate:** before publishing, run the sweep and confirm every remote branch is
clean. A dirty branch is a leak that would enter `main` if it merged; its owner
is named in the report so it can be fixed before publication.

## Packaging

`scripts/package.py` builds the release archive from an explicit allowlist of
plugin manifest files — nothing else. A listed path that is missing, symlinked,
escaping or generated is refused rather than skipped; the built archive is
scanned for internal residue and secrets and discarded if any are found; a
SHA-256 checksum is written next to the archive.

## Publication

Publication is a separate, authorised step. It is blocked until licensing is
decided and the live acceptance checks pass. Making the repository public is
not a side effect of any other step.
