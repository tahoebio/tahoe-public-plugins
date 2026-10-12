# Finding the served data catalog

The server maintains the scientific catalog and table definitions. Call
`list_releases()` for the selected public Tahoe-100M release and approved table
aliases, then `get_guide()` for current topics and `guide_version`. The plugin
routes to that catalog; it does not publish a parallel scientific inventory.

| Need | Server guide topic |
|---|---|
| Current data scope | `what-is-served` |
| Release and coverage | `establish-the-release`, `coverage-traps` |
| Treatment conditions and vehicle matching | `conditions-and-controls` |
| Gene identifiers | `genes` |
| Pseudobulk expression | `expression-grain-and-measurement` |
| Per-cell expression routes, columns, units and joins | `table-reference`, `querying-with-run-sql` |
| Released DE and its statistics | `differential-expression` |
| Pathway scores and gene-set vocabulary | `pathway-scores` |
| Classifier feature rankings | `response-markers` |
| Survival, arrest, Gini and Augur definitions | `phenotype-readouts` and returned provenance |
| Embeddings and centroid grain | `embedding-distances` |
| Citation | `citation-and-provenance` |

Confirm actual identifiers and measured coverage with `search_conditions`,
`resolve_genes`, `list_cell_lines` and `search_gene_sets`. The public tools use
registered release tables; approved SQL queries them in place. Read the server
catalog for current routes rather than assuming a plugin-shipped schema.

`get_expression_slice` serves pseudobulk expression. Use `run_sql` for aggregate
summaries over the advertised `single_cell_expression` table. Results are
bounded to 1,000 rows / 40 KB; a full single-cell matrix or per-cell embedding
export is outside this service. These output limits are not scan-cost limits.

For DE, use the released `log2FoldChange` described by `differential-expression`;
do not add a control mean to reconstruct expression from it. For phenotype
scores, use the server's definition and result provenance for the selected
phenotype; survival, Gini, arrest and Augur are different statistics.

Other Tahoe datasets, clinical or adverse-event data, and external reference
panels are outside this service. Report unavailable coverage explicitly.
