# Public tool contract

> **Stub.** The tool contract is finalised with the service (R1/R6).

The public Tara service exposes a small, read-only set of tools. Names and
schemas are versioned with the dataset release.

## Planned tools

| Tool | Purpose |
|------|---------|
| `health` | Report service availability and the served release. |
| `list_releases` | List the dataset releases available for retrieval. |
| `search_conditions` | Search condition metadata. |
| `resolve_genes` | Resolve gene identifiers, reporting ambiguity explicitly. |
| `get_expression_slice` | Retrieve a bounded expression slice. |

## Contract properties

- All tools are read-only and carry read-only annotations.
- Client-supplied SQL, table names, storage paths, URLs and code are rejected.
- Results carry provenance: release, filters, measurement semantics,
  missing-value meaning and a repeatable request manifest.
- Stable ordering: repeating a request against the same release returns
  equivalent data.
- Limits and errors are explicit; a partial result is never presented as
  complete.

The precise input/output schemas, bounds and error contract are added once the
service is live.
