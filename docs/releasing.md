# Releasing

> **Stub.** The release process is finalised with the release (R6).

## Validation

`scripts/validate.py` checks the manifests against the vendored Agent Plugins
schemas, enforces layout and version invariants, and scans tracked files for
internal residue and secrets.

## Packaging

`scripts/package.py` builds the release archive from approved tracked files
only. It refuses escaping symlinks, hidden paths and generated output rather
than skipping them, and writes a SHA-256 checksum next to the archive.

## Publication

Publication is a separate, authorised step. It is blocked until licensing is
decided and the live acceptance checks pass. Making the repository public is
not a side effect of any other step.
