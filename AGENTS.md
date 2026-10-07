# Repository guidance for agents

This repository is the public Tahoe Bio plugin catalog. Treat it as
**public-safe by construction**: every tracked file may one day be published.

## Hard rules

- Nothing internal: no private hostnames, identifiers, paths, or dataset tables
  beyond the approved public ones.
- Private planning documents are never committed here.
- Licensing is unresolved. Do not add a `LICENSE` file or a `license` field.
- Do not ship an active server configuration until the service host exists; a
  missing deployment configuration must fail clearly.
- Source manifest field names from the vendored schemas in `schemas/`; do not
  invent fields.

## Before proposing a change

```sh
uv sync
uv run pytest
uv run python scripts/validate.py
```
