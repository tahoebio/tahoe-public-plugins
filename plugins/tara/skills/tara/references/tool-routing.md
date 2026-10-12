# Tool routing — the long form

Read this when you need a tool's arguments, a worked call, or the full response
contract. The short routing table is in `SKILL.md`. Every tool here is on the
live service; nothing that is not yet served is named.

## Routing, with arguments

| Question | Sequence |
|---|---|
| Is the service up? Which release? | `health()` then `list_releases()` |
| Which drugs or doses are covered? | `search_conditions(limit=...)`; inspect truncation and narrow filters or raise the limit |
| Is drug X, or dose d, in the release? The exact label? | `search_conditions(query=<substring>)`, then confirm the label verbatim |
| Several drug labels at once? | `search_conditions(drugs=[...])` (batch) |
| Which conditions belong to one drug? | `search_conditions(drug=<exact label>)` |
| Is gene G in the release? Symbol vs Ensembl id? | `resolve_genes(symbols=[...])` |
| Which cell lines exist, or lines of one organ? | `list_cell_lines(organ=...)`, `list_cell_lines(query=...)` |
| A drug's targets, mechanism class, approval or trial status | `get_drug_info(drug=...)`, or filter by `moa=` or `target=` (a filter is required) |
| Differential expression, drug vs same-plate vehicle | `get_differential_expression(drug=[...], cell_lines=[...], genes=[...])`; without `genes`, the top `top_n` per contrast |
| Which gene sets are scored, or which collection? | `search_gene_sets(query=..., collection=..., limit=...)`; verify the set name, not just a familiar prefix |
| Drug-versus-vehicle pathway activity | `get_pathway_scores(gene_sets=[...], drug=[...], cell_lines=[...], dose=..., limit=...)`; scores are already differential |
| Condition-level survival, phase arrest, Gini or Augur | `get_phenotype_scores(drug=[...], cell_lines=[...], phenotypes=[...], dose=..., limit=...)`; read the selected phenotype's semantics |
| Treatment distance from matched vehicle in embedding space | `get_embedding_distance(drug=[...], cell_lines=[...], dose=..., limit=...)`; preserve plate and contributing cell counts |
| Genes most important for one drug in one line (importance, not direction) | `get_perturbation_markers(drug=..., cell_line=...)` |
| Expression of gene(s) under a treatment | `resolve_genes` -> `search_conditions` -> `get_expression_slice(genes=[...], conditions=[<label>], include_matched_controls=true)` |
| How do I interpret a score, a control, or the citation? | `get_guide(topic=...)` (omit `topic` for the whole guide) |
| A call returned `pending`; how do I fetch it? | call the **same** tool with the **same** arguments plus `result_handle` |
| Stop a running call | `cancel_execution(cancel_handle=<from the pending response>)` |
| Tell the maintainers something | `send_feedback(text=...)` (optional) |
| A join, aggregation or table a bounded tool does not expose | `run_sql(statement, max_rows)` (see `references/sql-guidance.md`) |
| Per-cell expression at scale | `run_sql` over `single_cell_expression`, bounded |
| Per-cell embeddings, bulk download | not served; the public Hugging Face release |
| Plate-level centroid vectors | `run_sql` over the advertised centroid table; vectors are distinct from the scalar distance-tool output |
| Anything outside Tahoe-100M | not available through these tools |

## Worked calls

One example per tool, with the argument keys the live schema accepts.

```text
list_releases()                          # name the release and its aliases first
health()                                 # only to confirm the service is up
search_conditions(drug="DMSO_TF")        # the vehicle arm of one drug label
search_conditions(query="DMSO", limit=20)# find arms by a drug-label substring
resolve_genes(symbols=["TP53", "EGFR"])  # symbol -> gene label + Ensembl id
get_expression_slice(genes=["TP53", "EGFR"], conditions=["Trametinib"])
get_expression_slice(
    genes=["TP53"], conditions=["Trametinib"],
    measurement="raw_counts", include_matched_controls=true,
)
list_cell_lines(organ="Lung")            # discover cell-line ids and names
get_drug_info(target="EGFR")             # drugs annotated against a gene
get_differential_expression(drug=["Trametinib"], cell_lines=["A549"], top_n=20)
search_gene_sets(collection="HALLMARK", limit=100)
get_pathway_scores(gene_sets=["HALLMARK_APOPTOSIS"], drug=["Trametinib"], cell_lines=["A549"])
get_phenotype_scores(drug=["Trametinib"], cell_lines=["A549"], phenotypes=["survival"])
get_embedding_distance(drug=["Trametinib"], cell_lines=["A549"])
get_perturbation_markers(drug="Trametinib", cell_line="A549")
get_guide()                              # the whole guide
get_guide(topic="conditions-and-controls")   # one guide section
cancel_execution(cancel_handle="<cancel_handle from the pending response>")
send_feedback(text="...", task_category="exploration", useful=true)
run_sql(statement="SELECT count(*) AS n FROM drug_metadata", max_rows=100)
```

## Response contract

Every result carries `ok`, `status` and the `release`. A data result also
carries:

- `provenance` — units, normalization, aggregation and what a zero means.
- `manifest` — tool, canonical arguments, release and server version, so a call
  can be replayed and attributed.
- `truncated` and `truncation_reasons` — `complete` is true only when nothing was
  trimmed.
- `pending` — the query outran the submit wait. Call the **same** tool again with
  the **same** arguments and `result_handle` set to the pending response's
  handle; do not resubmit. A handle is bound to the tool, release and arguments
  that produced it, so a handle from another tool, another release or another
  account reads as `not_found`.

`search_conditions` and `resolve_genes` report their own `release` and arguments
instead of a `manifest`.

## Errors worth recognizing

| `error_type` | Meaning |
|---|---|
| `bad_request` | An argument is out of range or malformed. |
| `not_found` | The named condition, gene, topic or handle is not in the release. |
| `rate_limited` | Too many calls; wait and retry. |
| `too_large` | The request exceeds a bound; narrow it. |
| `missing_identity` | Sign in through the connector, then retry. |
| `table_not_allowed` | A `run_sql` statement named a table that is not approved. |
| `filter_required` | A `run_sql` statement read a large table without a literal key filter. |
| `query_too_costly` | A `run_sql` statement used a cross join, an unqualified join, or too many tables. |
| `function_not_allowed` | A `run_sql` statement used a refused function or table source. |

A failure is `ok=false` with a fixed message that never echoes your input. A
truncated success is `ok=true` with `truncated=true`: report it as partial, never
as complete.

## Guide topics

`get_guide(topic=...)` accepts a topic id and returns just that section; the
response lists the available `topics` and the `guide_version`. Read the relevant
section before drawing a conclusion.

Also read `references/data-catalog.md` for the scientific caveats attached to
these routes. In particular, differential pathway scores are not absolute
activity, classifier importance and distance have no direction, and phenotype
scores are not interchangeable statistics. Verify the current topic list rather
than assuming an older guide covers a newly advertised tool.

## SQL

A bounded tool first. When no bounded tool fits a join, an aggregate or a table
they do not expose, use `run_sql(statement, max_rows)` — one read-only query over
the approved tables, guarded server-side. The tables, keys, joins, pitfalls and
query rules are in `references/sql-guidance.md`.
