# Public tool contract

The public Tara service exposes a small, read-only set of tools over the public
Tahoe-100M release. Names and schemas are versioned with the dataset release.

## Tools

| Tool | Purpose |
|------|---------|
| `health` | Report service availability and the served release. |
| `list_releases` | List the dataset releases available for retrieval. |
| `search_conditions` | Search the treatment conditions (drug x dose arms). |
| `resolve_genes` | Resolve gene identifiers, reporting ambiguity explicitly. |
| `get_expression_slice` | Retrieve a bounded pseudobulk expression slice. |
| `list_cell_lines` | List the cell lines (Cellosaurus id, name, organ, driver annotations). |
| `get_drug_info` | Drug annotations: targets, mechanism class, approval and trial status. |
| `get_differential_expression` | Per-gene differential expression, drug versus same-plate vehicle. |
| `search_gene_sets` | Discover scored gene-set names and collections; names do not establish gene membership. |
| `get_pathway_scores` | Retrieve differential VISION scores with the matched vehicle already subtracted. |
| `get_phenotype_scores` | Retrieve phenotype-specific statistics, with their direction and significance semantics. |
| `get_embedding_distance` | Distance from treatment to its plate- and line-matched vehicle centroid, not a directional effect. |
| `get_perturbation_markers` | Genes a classifier found most important for one drug in one cell line (importance, not direction). |
| `get_guide` | Return the analysis guidelines and data catalog, whole or by topic. |
| `run_sql` | Run one read-only SQL query over the approved tables, guarded server-side. |
| `cancel_execution` | Cancel a still-running call, using its `cancel_handle`. |
| `send_feedback` | Send optional feedback about the service. |

The data tools are read-only. `run_sql` is read-only too, but it accepts
client-supplied query text: the statement is parsed and refused unless it is one
`SELECT`/`WITH`/`UNION` over the approved tables, with a selective filter on any
large table and no cross join. `cancel_execution` and `send_feedback` act only on
the caller's own state and are not reads.

## Not yet served

| Tool | Purpose |
|------|---------|
| `list_dataset_products` | Approved pinned products and row grain; available once the server advertises it. |
| `prepare_dataset` | Account-bound renewable access for native readers; available once the server advertises it. |

Bulk file or Arrow reads use a separate metered data API. These tools are not
claimed live until the server advertises them. Preparing access changes only
the caller's access lease; it does not change dataset contents.

## Contract properties

- All data tools are read-only and carry read-only annotations.
- Client-supplied storage paths, URLs and code are rejected. `run_sql` accepts
  SQL, but only one read-only statement over the approved tables.
- Results carry provenance: release, filters, measurement semantics,
  missing-value meaning and a repeatable request manifest.
- Stable ordering: equivalent requests against unchanged source data return
  equivalent data. A release label and request manifest do not themselves pin
  immutable table versions; retain source-version evidence when available.
- Limits and errors are explicit; a partial result is never presented as
  complete.
- A long call may return `pending` with a `result_handle`; the same tool is
  called again with that handle to fetch the finished result.

The precise input and output schemas, bounds and error vocabulary are declared
by the live service and reported on each result.
