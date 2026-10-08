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
