# The served Tahoe-100M dataset

What this server serves, and how to read it. This is a routing and
interpretation map, not an inventory: confirm what a release contains with
`list_releases`, `search_conditions` and `resolve_genes` rather than assuming.

## What is served

One bounded, read-only slice of the public **Tahoe-100M** release, reached only
through this server's tools. There is no SQL, no direct table or file access, and
no client-supplied query text. Every tool is read-only and runs as the service's
own read identity, so the release is the same for every caller. Responses are
bounded to a fixed byte ceiling: a truncated response says so, and narrowing the
request is the only way to see more.

## Establish the release

`health()` reports liveness and the served release without touching any data; it
is the cheapest way to confirm the service is up before a longer call.

`list_releases()` names the release and the table aliases this server serves. The
`release` value it returns appears on every result, so a caller can pin exactly
what it saw. A newer release is a scientific source change, not just a new label:
re-establish semantics and coverage when the release changes.

## Conditions and controls

`search_conditions()` lists the treatment conditions -- the drug-by-dose arms --
the release contains. Use it to find the `drug` values to pass to
`get_expression_slice`. It accepts an exact `drug` label, an optional exact
`dose`, and an optional `query` substring matched against drug labels, and pages
with `limit` (1 to 500, default 50).

The vehicle arm is the control. Its `dose` is 0, and its drug label is the
vehicle label the release uses (`DMSO_TF`); it is a control, never a treatment.
Set `include_matched_controls` on `get_expression_slice` to also receive the
vehicle rows matched to the requested treatments on the same gene, plate and
cell_line, flagged `is_control = true`.

## Genes

`resolve_genes()` maps a symbol or an Ensembl id to the release's own gene label.
It reports `exact`, `ambiguous` or `not_found`, and never guesses: a symbol it
reports `not_found` is not in the release, and an `ambiguous` symbol must be
disambiguated before use. Use the resolved label in `get_expression_slice` so the
request names a gene the release actually carries.

## Expression grain and measurement

`get_expression_slice()` returns pseudobulk expression for bounded sets of genes
and conditions. Each row is one `(gene, sample_id, cell_line)` aggregate with its
`drug`, `dose`, `plate` and `n_cells` inline -- not a single cell and not a
replicate. Several `sample_id` values share one drug-by-dose arm, so a per-arm
statistic must be computed over the aggregates of that arm, never assumed from
the row count.

Choose the measurement with `measurement`: `cpm_log1p` (default) or
`raw_counts`. The returned value column is named after the choice, and the
`provenance` block on every result states the units, normalization, aggregation
and what a zero means, so a figure can cite it. This is expression, not fold
change: a treatment-versus-control contrast is computed by the analyst from the
aggregates and the matched control rows, and is labelled as such.

Every `get_expression_slice` result carries a `manifest` naming the tool, the
canonical arguments, the release and the server version. Repeating a call with
the same arguments reproduces it, so a result can be replayed and attributed.

## Coverage traps

- Presence in a compound library is not coverage in the release. Confirm an arm
  exists with `search_conditions` before a question or request assumes it.
- Panel drug names appear as free base and as salt form. Count and ranking
  questions over drugs must dedupe to the parent or active moiety, or one drug
  counts twice and top-N rankings shift.
- Drug and cell-line labels are case-sensitive and may be lowercase or carry a
  salt suffix. Confirm the exact label with `search_conditions(query=...)` before
  a request assumes it, and use the label verbatim.
- The served panel is cancer cell lines plus at least one immortalized normal
  line; exclude or note the normal line before making a pan-cancer claim. The
  same caution applies to genotype and lineage strata, where n can be thin.
- A substring match on the vehicle label also selects real treatments whose
  labels contain that substring as a salt. Match the vehicle as the exact label,
  not a substring.
- A missing row is not zero. Sparse omissions mean zero only inside the verified
  measured gene and condition axes; an unmeasured gene or an absent condition is
  unavailable, not zero.
- Coverage facts are release-specific, so re-check them when the release changes.

## Working with the public files

Per-cell expression is reachable two ways: a bounded `run_sql` query over
`single_cell_expression` (clustered by cell line and sample — filter both), or
the public Hugging Face release
([tahoebio/Tahoe-100M](https://huggingface.co/datasets/tahoebio/Tahoe-100M)).
Per-cell embeddings are **not** served, only the plate-level centroids. In the
public files, element 0 of a tokenized row is `<CLS>` — drop it before zipping
tokens to genes — and the vehicle label must be matched exactly (`DMSO_TF`),
never by substring.

## Citation and provenance

Tahoe-100M is public: Zhang et al. (2025), "Tahoe-100M: A Giga-Scale Single-Cell
Perturbation Atlas for Context-Dependent Gene Function and Cellular Modeling",
bioRxiv [10.1101/2025.02.20.639398](https://doi.org/10.1101/2025.02.20.639398);
CC0 release on
[Hugging Face](https://huggingface.co/datasets/tahoebio/Tahoe-100M) and the
[Arc Virtual Cell Atlas](https://arcinstitute.org/tools/virtualcellatlas). Cite
the release when asked about provenance.

## What these tools do not serve

Only the public Tahoe-100M release is served -- one drug panel (379 treatments,
3 doses, vehicle `DMSO_TF`), one 50-line cell panel, 14 plates. There is no SQL,
no file or table browsing, and no client-supplied query text; a request for a
table, path or query is refused. Not available, so do not search for it here:
other Tahoe screens or unreleased datasets; clinical or adverse-event data;
proprietary external reference panels (dependency, viability or signature
databases) joined to this release; unreleased compound annotations beyond the
released drug metadata; per-cell expression matrices and per-cell embeddings
(public in the Hugging Face release, not through these tools); embedding vectors
themselves (distances only); the "absolute" pathway-score run (a centred
duplicate of the differential scores); wide per-line matrices (request rows and
pivot); internal cell-line codes (results carry Cellosaurus ids and names). If a
question needs one of these, say so and stop; do not substitute a different
population, measurement or dataset silently.
