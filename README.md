# Tahoe Bio Plugins

Private preview — not published, not a supported release.

The Git-based plugin catalog for Tahoe Bio's public agent plugins. Its first
plugin is **Tara**, which connects your own agent to the public Tahoe-100M
dataset service.

> **Status: private preview.** Nothing here is published, supported or licensed.
> The plugin ships the `tahoe-public` server endpoint; the clean-machine install
> and sign-in have not yet been verified end to end (see
> `docs/install-verification.md`).

## Install

The plugin is the way in. It connects your agent to the `tahoe-public` MCP
server; the service then delivers the data and the guidance for using it.

### Codex CLI

```sh
codex plugin marketplace add tahoebio/tahoe-public-plugins
codex plugin add tara@tahoe-public
```

### Claude Code

```sh
claude plugin marketplace add tahoebio/tahoe-public-plugins
claude plugin install tara@tahoe-public
```

Either way, complete the GitHub sign-in that the client opens, then **reload the
plugin or start a new session** so the tools appear. Full steps, including the
one-prompt variant and the advanced direct-server option, are in
`docs/install.md`.

## Layout

| Path | Purpose |
|------|---------|
| `.agents/plugins/marketplace.json` | Codex marketplace catalog. |
| `.claude-plugin/marketplace.json` | Claude marketplace catalog. |
| `plugins/tara/plugin.json` | Portable plugin manifest (Codex). |
| `plugins/tara/mcp.json` | Portable MCP configuration (Codex). |
| `plugins/tara/.claude-plugin/plugin.json` | Native Claude manifest, MCP inline. |
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

## Data and guidance

The Tahoe-100M **data is CC0** — free to use. The **guidance is proprietary**
and is delivered by the service at runtime; it is not distributed as files in
this repository. See `docs/data-and-licensing.md`.

## Licence — placeholder, not a decision

> **No licence has been chosen.** This is a deliberate placeholder, not an
> oversight and not a choice.

There is **no LICENSE file and no `license` field** anywhere in this
repository. The software, documentation, dataset and trademark rights are
distinct and are not yet decided. Nothing here may be published or
redistributed, and no licence may be assumed, until that decision is recorded.
The decision is tracked as a named publication blocker. See
`docs/data-and-licensing.md`.
