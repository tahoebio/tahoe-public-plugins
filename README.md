# Tahoe Bio Plugins

The Git-based plugin catalog for Tahoe Bio's public agent plugins. Its first
plugin is **Tara**, which connects your own agent to the public Tahoe-100M
dataset service.

## Install

The plugin is the way in. It connects your agent to the `tahoe-public` MCP
server and ships the `tara` skill, which tells the agent how to route a
Tahoe-100M question to the right tool; the service then serves the data.

Follow the [served install guide](https://tara.tahoebio.io/install.md) for the
current Codex CLI and Claude Code setup and sign-in steps. You complete sign-in
with a verified email address or Google account in the browser opened by the client.

To ask your agent to follow that guide, paste its current prompt:

> Use curl to read https://tara.tahoebio.io/install.md and perform the setup to install Tara

For older connections and plugin-owned versus direct entries, see
[installation notes](docs/install.md). For a clean-machine check, see
[install verification](docs/install-verification.md).

## Layout

| Path | Purpose |
|------|---------|
| `.agents/plugins/marketplace.json` | Codex marketplace catalog. |
| `.claude-plugin/marketplace.json` | Claude marketplace catalog. |
| `plugins/tara/plugin.json` | Portable plugin manifest (Codex). |
| `plugins/tara/mcp.json` | Portable MCP configuration (Codex). |
| `plugins/tara/.claude-plugin/plugin.json` | Native Claude manifest, MCP inline. |
| `plugins/tara/skills/tara/SKILL.md` | The `tara` skill: routing and contract. |
| `plugins/tara/skills/tara/references/` | The skill's guide-topic map, data routes and tool calls. |
| `evals/tara/` | Public-safe eval prompt pack and rubric. |
| `docs/` | Public documentation. |
| `schemas/` | Vendored Agent Plugins schemas used by the offline tests. |
| `scripts/` | Validation and packaging tooling. |
| `tests/` | Offline test suite. |

## Development

```sh
uv sync
uv run pytest
uv run python scripts/validate.py
uv run python scripts/package.py --out dist
```

The leak/history scan is per-branch: CI judges the commit under test on its own
history, so one stale branch cannot fail an unrelated one. To widen the scan to
every ref locally, or to report every remote branch (the every-ref sweep), see
`docs/releasing.md`.

## Data and guidance

The Tahoe-100M **data is CC0** — free to use. The plugin ships the `tara` skill,
which routes questions to the public tools and loads scientific guidance
from `get_guide` at runtime. The data and the guidance are separate grants; see
`docs/data-and-licensing.md`.

## Licence

This repository combines parts with different rights. Each part carries the
licence below, and the full texts are in `LICENSE` (Apache-2.0),
`LICENSE-CC-BY-4.0` (CC BY 4.0) and `NOTICE` (attribution).

| Path | Licence (SPDX) |
|------|----------------|
| `plugins/tara/skills/**` — the `tara` skill and its references | `CC-BY-4.0` |
| `docs/**` — the public documentation | `CC-BY-4.0` |
| `schemas/**` — third-party schemas vendored from agent-plugins.org | `Apache-2.0` (upstream) |
| `plugins/tara/assets/tahoe-logo.png` — the Tahoe brand mark | Not licensed (all rights reserved) |
| Tahoe's plugin code, manifests, tooling, tests, CI, `evals/**` and root Markdown — every other path | `Apache-2.0` |

The **skill text and the documentation are CC BY 4.0**: reuse them, including
commercially, with attribution to Tahoe Bio. Tahoe's **code is Apache-2.0**:
reuse it under the same terms, with the patent grant that licence carries. The
vendored `schemas/**` are the third party's own files, licensed Apache-2.0
upstream; `schemas/provenance.json` records each source.

The Tahoe-100M dataset the service serves is a separate grant — **CC0-1.0** —
and is not stored in this repository. The service's runtime guidance, the
gene-set names, the `tahoe-logo.png` brand mark and the "Tahoe" and "Tara"
trademarks are not covered by either licence here; see
`docs/data-and-licensing.md`.
