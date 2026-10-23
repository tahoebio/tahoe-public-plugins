# Tahoe Bio Plugins

The Git-based plugin catalog for Tahoe Bio's public agent plugins. Its first
plugin is **Tara**, which connects your own agent to Tahoe's public dataset
service. The signed-in account's `list_releases()` response determines access.

## Install

The plugin is the way in. It connects your agent to the `tahoe-public` MCP
server and ships the `tara` skill, which tells the agent how to route a
question to the selected dataset's tools; the service then serves the data.
Tahoe-100M keeps its existing routes. Emerald Bay routes require server 0.4.0
or later and explicit Emerald capabilities in discovery. Installing this
plugin does not enable a dataset or grant access. If Emerald is absent, the
agent reports it unavailable instead of substituting Tahoe-100M.

### Codex CLI

Run these in a terminal, in order:

```sh
codex plugin marketplace add tahoebio/tahoe-public-plugins
codex plugin add tara@tahoe-public
codex mcp login tahoe-public      # opens the browser: Allow Access → Google
```

Then start a **new Codex session** so the tools load.

### Claude Code

```sh
claude plugin marketplace add tahoebio/tahoe-public-plugins
claude plugin install tara@tahoe-public
```

Restart Claude Code, then sign in with `/mcp` (or on first use).

### Ask your agent instead

Any agent that can add a plugin (it installs and stops; **you** sign in
yourself). Paste this prompt:

> Install the Tahoe plugin: add the marketplace tahoebio/tahoe-public-plugins, install the tara plugin, approving the permission prompt if asked. Then stop. Do not try to sign in or open a browser. Tell me to sign in myself and start a new session.

Full steps, including the advanced direct-server option, are in `docs/install.md`.

## Updates

> Install Tara from `tahoebio/tahoe-public-plugins` on the `main` channel (do
> not pin a version tag if you want updates). Claude Code: run
> `claude plugin marketplace add tahoebio/tahoe-public-plugins`, then
> `claude plugin install tara@tahoe-public`. Third-party marketplaces have
> auto-update **off by default**. In a Claude Code session run `/plugin` →
> **Marketplaces** → **tahoe-public** → **Enable auto-update**. Updates arrive
> after a session starts; use `/reload-plugins` when prompted or start a new
> session. To update now, run `claude plugin update tara@tahoe-public` in your
> shell, or select **Update marketplace** inside `/plugin`; the shell
> `claude plugin marketplace update` alone refreshes listings and does not
> update installed plugins. Codex CLI: run
> `codex plugin marketplace add tahoebio/tahoe-public-plugins --ref main`,
> `codex plugin add tara@tahoe-public`, then `codex mcp login tahoe-public` and
> start a new session. For later versions run
> `codex plugin marketplace upgrade tahoe-public` (or
> `codex plugin marketplace upgrade`) and start a new Codex session. Unattended
> Codex marketplace upgrades are not documented, so this explicit upgrade is the
> supported user path. Verify the installed Tara manifest shows `0.4.0`, then
> make a signed-in `list_releases` call and an Emerald call with
> `dataset="emerald-bay"`; Tahoe requests still work. Your account's release
> list is the access authority.

An organization **administrator**, not this repository, may centrally turn
Claude auto-update on using managed
`extraKnownMarketplaces["tahoe-public"]` with GitHub source,
`autoUpdate: true`, and `enabledPlugins["tara@tahoe-public"]: true`; that
requires a separate admin rollout and client repository read access.
[Claude install/update](https://code.claude.com/docs/en/discover-plugins),
[publisher guidance](https://code.claude.com/docs/en/plugins/host-marketplace),
[managed setting](https://code.claude.com/docs/en/plugins/org),
[marketplace source/ref](https://code.claude.com/docs/en/plugins/marketplace-reference),
[Codex package/marketplace CLI](https://developers.openai.com/plugins/build/plugins).

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

Tahoe-100M **source data is CC0**. Emerald Bay **source data is CC BY 4.0**
and requires attribution and identification of transformations. The plugin
ships the `tara` skill, which routes questions to the public tools and loads scientific guidance
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

The datasets have separate grants: Tahoe-100M is **CC0-1.0** and Emerald Bay
is **CC-BY-4.0**. Neither dataset is stored in this repository. The service's
runtime guidance, the gene-set names, the `tahoe-logo.png` brand mark and the "Tahoe" and "Tara"
trademarks are not covered by either licence here; see
`docs/data-and-licensing.md`.
