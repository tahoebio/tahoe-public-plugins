# Releasing

> **Stub.** The release process is finalised with the release (R6).

## Validation

`scripts/validate.py` checks the manifests and the MCP configuration against
the vendored Agent Plugins schemas, enforces layout and version invariants, and
scans both the working tree and the full git history for internal residue and
secrets. CI checks out the full history so the history scan covers every commit.

## Packaging

`scripts/package.py` builds the release archive from approved tracked files
only. It refuses escaping symlinks, hidden paths and generated output rather
than skipping them, scans the built archive for internal residue and secrets
and discards it if any are found, then writes a SHA-256 checksum next to the
archive.

## Publication

Publication is a separate, authorised step. It is blocked until licensing is
decided and the live acceptance checks pass. Making the repository public is
not a side effect of any other step.
