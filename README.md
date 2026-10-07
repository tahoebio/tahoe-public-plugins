# Tahoe Bio Plugins

Private preview — not published, not a supported release.

The Git-based plugin catalog for Tahoe Bio's public agent plugins. Its first
plugin is **Tara**, which lets a computational researcher discover and retrieve
bounded slices of the public Tahoe-100M dataset from their own agent.

> **Status: private preview.** Nothing here is published, supported or licensed,
> and the Tara plugin does not yet connect to a live service.

## Layout

| Path | Purpose |
|------|---------|
| `.agents/plugins/marketplace.json` | Marketplace catalog (canonical). |
| `.claude-plugin/marketplace.json` | Marketplace catalog (legacy-compatible mirror). |
| `plugins/tara/` | The Tara plugin: manifest and skill. |
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

## Licensing — named blocker

There is **no LICENSE file**. The software, documentation, dataset and
trademark rights are distinct and are not yet decided. Nothing here may be
published or redistributed, and no licence may be assumed, until that decision
is recorded. See `docs/data-and-licensing.md`.
