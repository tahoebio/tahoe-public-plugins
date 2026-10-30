# Public tool contract

Tara uses 18 shared tool names. Availability and scientific meaning depend on
the selected dataset and authenticated account. Call `list_releases()` first;
a registered tool name or installed plugin version does not establish access.

## Tools

| Tool | Purpose | Emerald Bay, when advertised |
|------|---------|-----------------------------|
| `health` | Report service availability and version. | Shared; health is not capability discovery. |
| `list_releases` | List releases and approved aliases. | Adds the account's available dataset, tools, measurements, score kinds and limits. |
| `search_conditions` | Resolve condition labels. | Retain sample and complete combination labels. |
| `resolve_genes` | Resolve genes, including ambiguity. | Distinguish measured axis, vocabulary-only and unknown genes. |
| `get_expression_slice` | Bounded pseudobulk expression. | Raw counts, whole-profile CPM and natural-log log1p(CPM), with endpoint controls. |
| `list_cell_lines` | Resolve cell-line identities. | Canonical line key, cross-references and identity uncertainty; no organ/driver filters. |
| `get_drug_info` | Drug/condition metadata. | Sample/condition metadata only; no targets, MOA, approval or structures. |
| `get_differential_expression` | Tahoe drug-versus-vehicle DE. | Unsupported. |
| `search_gene_sets` | Discover scored names and collections; validated readouts first when the panel is visible. | Differential VISION vocabulary; names do not establish membership; only readouts in this vocabulary are ranked. |
| `get_pathway_scores` | Differential pathway activity; `process` scores a validated readout, and each row names its `score_source` and `validation_status` when the panel is visible. | Differential VISION only; do not subtract controls again. Validation labels only; custom readouts are `gene_set_not_found`. |
| `get_phenotype_scores` | Dataset-specific phenotype values. | Released five-day growth response; no significance filter. |
| `get_embedding_distance` | Tahoe distance from matched vehicle centroid. | Unsupported. |
| `get_perturbation_markers` | Tahoe classifier feature importance. | Unsupported. |
| `get_guide` | Dataset-specific scientific guide and table catalog. | Separate topics, guide version and attribution. |
| `run_sql` | One guarded read-only query. | Only the selected dataset's approved aliases; includes bounded single-cell raw reads. |
| `cancel_execution` | Cancel an owned running query by handle. | Shared; no dataset argument. |
| `send_feedback` | Optional user-requested feedback. | Shared; no dataset argument. |
| `get_validated_signatures` | Validated readout for a cancer process, what a gene set was tested for, and evidence by validation arm. Registry only; server 0.5.0 and the panel in discovery. | No dataset argument. Validation never used Emerald Bay data. |

## Not yet served

No additional tool names are proposed. Emerald is an optional capability of the
existing tools and is available only when the server advertises it to the caller.

## Dataset selection and compatibility

- Preserve existing Tahoe-100M calls without the new selector. The base server
  compatibility floor remains 0.3.9. Omission selects Tahoe; it must never be
  used to retry a failed Emerald request.
- Emerald requires server 0.4.0 or later **and** a successful, untruncated
  `list_releases` entry for `emerald-bay`, advertising the requested tool,
  measurement/score kind and aliases. `health` can recover a server version but
  cannot replace those capabilities. An older, unavailable or unadvertised
  Emerald route stops with an explicit limitation.
- Pass `dataset="emerald-bay"` to Emerald data, SQL and guide calls, including
  pending-result polling. The discovery and operational tools have no dataset
  argument. Keep each dataset's guide and result provenance separate.
- Resolve sample, line, gene and gene-set identifiers before querying. Preserve
  complete combination conditions and each control replicate. Do not silently
  drop unsupported dose, organ, driver, target or significance filters.
- Emerald excludes DESeq2 expression, DE, absolute VISION, embeddings and
  perturbation markers. Unavailability is not a zero measurement. The source
  label `survival` maps to `growth_rate_released`, not clinical survival or a
  Tahoe phenotype. Consult the selected guide for units and populations.
- The validated-signatures panel requires server 0.5.0 or later **and**
  `validated_signatures` on the Tahoe-100M `list_releases` entry. The server
  default is off: without the entry, `get_validated_signatures` and `process`
  return `not_found` and no gene set is validated. Named `gene_sets` requests
  keep working on every version.

## Contract properties

Data tools and `run_sql` are read-only. SQL is parsed and refused unless it is
one permitted read over approved aliases with required selective filters and
join constraints. Cross-dataset joins, writes, file sources and unbounded
exports are outside the contract. `cancel_execution` and `send_feedback` act on
the caller's operational state and are not data reads.

Check `ok`, status, release, provenance, repeatable manifest and truncation.
A long call can return `pending`; poll the same tool, dataset and effective
arguments with `result_handle`. Handles are tied to account, tool, release and
arguments. Recheck access failures without changing the dataset. Cancellation
uses its separate handle and does not claim a dataset release.

Output is capped at 1,000 rows / 40 KB; those limits are not scan-cost limits.
A truncated success is partial. Narrow or aggregate it; do not page around the
ceiling. Stable ordering supports replay, but a release label is not by itself
proof of immutable source versions. Keep source revision evidence when returned.

The live schemas, discovery response and selected guide define the current
contract. Structured plugin examples are checked offline against a public-safe
schema snapshot; this does not establish actual host behavior or live data
correctness. Fresh host/MCP acceptance remains required.
