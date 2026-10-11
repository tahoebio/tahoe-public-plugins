# Changelog

All notable changes to this repository are recorded here. This project adheres
to semantic versioning.

## 0.1.0 — unreleased

Initial repository skeleton.

- Marketplace catalog (`tahoe-public`) with the `tara` plugin.
- Plugin manifest and a draft skill placeholder (science review pending).
- Public documentation stubs.
- Validation, residue scanning and packaging scripts.
- Offline test suite and CI workflow.

### Packaging, docs, CI and leak scans (R6)

- Remote MCP server shipped as `tahoe-public` (`streamable-http` at
  `https://tara.tahoebio.io/mcp`) with no embedded credentials.
- Install documented as a single Codex CLI command, plus the Codex "Run without
  daemon" note; Codex CLI is the only tested host.
- Clean-machine install verification prepared for a human tester.
- Validation now covers the MCP configuration; residue and secret scanning now
  also covers the built archive and the full git history.
- Packaging discards an archive that contains residue or secrets.
- Licence remains an explicit placeholder — no LICENSE file, no `license` field.

### Leak-guard hardening (review)

- Every scanner pattern is now assembled from fragments, so `scripts/common.py`
  contains no forbidden literal and is scanned like any other file — the
  path-based exclusion is gone from both the working-tree and history scans.
- The history parser handles commit bodies without a trailing newline (as
  GitHub squash commits produce), tracks hunk line numbers, and reads binary
  changes.
- Content that cannot be read as text is reported, not skipped, in the working
  tree, the archive and history; a binary member now fails the release build.
- Packaging refuses a symlinked path component, so a symlinked parent directory
  can no longer pull files in from outside the checkout.
- Validation fails when history cannot be read in full (no repository, or a
  shallow clone).

### Per-branch leak scan (CI)

- The history scan is now a function of the commit under test: `scan_history`
  scans the history reachable from `HEAD` by default, so one stale branch can no
  longer fail every unrelated branch and `main`. `--all-refs` (and
  `scan_history(all_refs=True)`) restores the whole-repository sweep as an
  explicit developer option.
- `scripts/sweep_branches.py` runs the same per-ref scan once for every remote
  branch and prints a report — branch, tip, offending commit, author, pass/fail —
  exiting 0. It backs the pre-publication gate ("every remote branch's scan is
  green") and runs on `workflow_dispatch` and a weekly schedule. It fails
  loudly when it cannot do its job: a fetch it cannot read, or no branches found.
- The history scan runs `--full-history`, so a commit on a merged parent that a
  merge resolution reverted is still scanned; binary findings carry their commit,
  so the report names the author.
- CI triggers on pushes to every branch **and on tag pushes** (a tag can point
  outside every branch tip's ancestry), plus pull requests.

### Thin plugin (no guidance payload)

- The plugin now ships connection manifests only: the portable Codex pair
  (`plugin.json`, `mcp.json`), a native Claude manifest
  (`plugins/tara/.claude-plugin/plugin.json`) and two catalogs — the Codex
  catalog and an owner-bearing Claude catalog.
- The `skills/` payload is gone. Scientific guidance is served by the service at
  runtime and is not distributed as files here.
- Catalogs are no longer required to be byte-identical; each host's shape is
  validated, and the two must agree on identity and on the plugin directory
  they resolve.
- The release archive is an explicit allowlist of manifest files (dotfiles
  included), not a directory prefix.
- Install docs lead with the plugin marketplace path for Codex and Claude, with
  the one-prompt variant and a direct `mcp add` as an advanced fallback.
- Data is CC0; guidance is proprietary and served at runtime. The licence
  remains a placeholder pending S11.
