# Repository guidance for agents

This repository is the public Tahoe Bio plugin catalog. Treat it as
**public-safe by construction**: every tracked file may one day be published.

## Hard rules

- Nothing internal: no private hostnames, identifiers, paths, or dataset tables
  beyond the approved public ones.
- Private planning documents are never committed here.
- Licensing is decided and recorded in `LICENSE` (Apache-2.0 for code),
  `LICENSE-CC-BY-4.0` (CC BY 4.0 for `skills/**` and `docs/**`) and `NOTICE`.
  Keep both manifests' `license` field equal to the code licence, and never
  change the licence choices or repository visibility.
- The MCP configuration points only at the approved public host
  (`https://tara.tahoebio.io/mcp`). Never ship a stand-in host, and never embed
  credentials in it.
- Source manifest field names from the vendored schemas in `schemas/`; do not
  invent fields.

## Before proposing a change

```sh
uv sync
uv run pytest
uv run python scripts/validate.py
```
