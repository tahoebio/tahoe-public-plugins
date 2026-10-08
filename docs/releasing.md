# Releasing

> Validation, packaging and the leak scans are in place. Publication itself is
> still blocked (see below).

## Validation

`scripts/validate.py` checks the manifests and the MCP configuration against
the vendored Agent Plugins schemas, enforces layout and version invariants, and
scans both the working tree and the full git history for internal residue and
secrets. CI checks out the full history so the history scan covers every commit.

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
