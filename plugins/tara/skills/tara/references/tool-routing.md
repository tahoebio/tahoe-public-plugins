# Tool routing — the long form

Read this when you need a tool's arguments, a worked call, or the full response
contract. The short routing table is in `SKILL.md`. The 18 tool names are
shared. Dataset availability and supported measurements must be discovered for
the signed-in account before using a route. Emerald examples require server
0.4.0 or later and an advertised Emerald capability; they are not an access claim.
Validated-signature examples require server 0.5.0 or later and
`validated_signatures` on the Tahoe-100M `list_releases` entry.

## Tahoe-100M routing, with arguments

| Question | Sequence |
|---|---|
| Is the service up? Which release? | `health()` then `list_releases()` |
| Which drugs or doses are covered? | `search_conditions(limit=...)`; inspect truncation and narrow filters or raise the limit |
| Is drug X, or dose d, in the release? The exact label? | `search_conditions(query=<substring>)`, then confirm the label verbatim |
| Several drug labels at once? | `search_conditions(drugs=[...])` (batch) |
| Which conditions belong to one drug? | `search_conditions(drug=<exact label>)` |
| Is gene G in the release? Symbol vs Ensembl id? | `resolve_genes(symbols=[...])` |
| Which cell lines exist, or lines of one organ? | `list_cell_lines(organ=...)` or `list_cell_lines(query=...)`; prefer the returned `cell_line` (`CVCL_...`) for reproducible data calls; data tools also accept exact cell-line names |
| A drug's targets, mechanism class, approval or trial status | `get_drug_info(drug=...)`, or filter by `moa=` or `target=` (a filter is required) |
| Differential expression, drug vs same-plate vehicle | `get_differential_expression(drug=[...], cell_lines=[...], genes=[...])`; without `genes`, the top `top_n` per contrast |
| Which gene set reads out a pathway or program? What was a set tested for? | `get_validated_signatures(process=...)`, `query=...` or `gene_set=...`; registry only, no `dataset`; no argument lists every process |
| Which gene sets are scored, or which collection? | `search_gene_sets(query=..., collection=..., limit=...)`; validated readouts are listed first; verify the set name, not just a familiar prefix |
| Drug-versus-vehicle pathway activity | `get_pathway_scores(process=..., drug=[...], cell_lines=[...])` for the validated readout, or `gene_sets=[...]` for a named set; scores are already differential; read each row's `score_source` and `validation_status` |
| Condition-level survival, phase arrest, Gini or Augur | `get_phenotype_scores(drug=[...], cell_lines=[...], phenotypes=[...], dose=..., limit=...)`; read the selected phenotype's semantics |
| Treatment distance from matched vehicle in embedding space | `get_embedding_distance(drug=[...], cell_lines=[...], dose=..., limit=...)`; preserve plate and contributing cell counts |
| Genes most important for one drug in one line (importance, not direction) | `get_perturbation_markers(drug=..., cell_line=...)` |
| Expression of gene(s) under a treatment | `resolve_genes` -> `search_conditions` -> `get_expression_slice(genes=[...], conditions=[<label>], include_matched_controls=true)` |
| How do I interpret a score, a control, or the citation? | `get_guide(topic=...)` (omit `topic` for the whole guide) |
| A call returned `pending`; how do I fetch it? | call the **same** tool with the **same** arguments plus `result_handle` |
| Stop a running call | `cancel_execution(cancel_handle=<from the pending response>)` |
| Tell the maintainers something | `send_feedback(text=...)` (optional) |
| A join, aggregation or table a bounded tool does not expose | `run_sql(statement, max_rows)` (see `references/sql-guidance.md`) |
| Aggregates over per-cell expression | `run_sql` over advertised `single_cell_expression`; 1,000 rows / 40 KB, not a cell-matrix export |
| Per-cell embeddings, bulk download | not served; offer `get_embedding_distance` for the matched-vehicle shift |
| Plate-level centroid vectors | `run_sql` over the advertised centroid table; vectors are distinct from the scalar distance-tool output |
| Another dataset | select it only if discovery advertises it; see Emerald routing below |

## Worked calls

Tahoe-100M calls retain the legacy arguments. Omit the new `dataset` argument
on older servers. The examples below do not establish Emerald capabilities.

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
list_cell_lines(query="A549")             # resolve a name to CVCL_0023
list_cell_lines(organ="Lung")             # discover lines by organ
get_drug_info(target="EGFR")             # drugs annotated against a gene
get_differential_expression(drug=["Trametinib"], cell_lines=["CVCL_0023"], top_n=20)
search_gene_sets(collection="HALLMARK", limit=100)
get_pathway_scores(gene_sets=["HALLMARK_MTORC1_SIGNALING"], drug=["Trametinib"], cell_lines=["CVCL_0023"])
get_phenotype_scores(drug=["Trametinib"], cell_lines=["CVCL_0023"], phenotypes=["survival"])
get_embedding_distance(drug=["Trametinib"], cell_lines=["CVCL_0023"])
get_perturbation_markers(drug="Trametinib", cell_line="CVCL_0023")
get_guide(topic="establish-the-analysis-contract")  # starting guidance, topics and version
get_guide()                              # optional full guide
get_guide(topic="conditions-and-controls")   # one guide section
cancel_execution(cancel_handle="<cancel_handle from the pending response>")
send_feedback(text="...", task_category="exploration", useful=true)
run_sql(statement="SELECT count(*) AS n FROM drug_metadata", max_rows=100)
```

`HALLMARK_MTORC1_SIGNALING` is the validated mTORC1 readout, so the panel
serves its scores; an older server or a hidden panel serves the released
VISION store, without a validation label.

## Validated signature worked calls

The Tahoe Signatures panel (release `tahoe-signatures/v02`) names one validated
readout per cancer process. It is on only when `list_releases()` shows
`validated_signatures` on the Tahoe-100M entry; otherwise these calls return
`not_found`, and every gene set is unvalidated. The process names and aliases
come from the registry: call `get_validated_signatures()` with no argument to
list them.

Look up a process's readout, direction class, evidence by arm, caveats and
tested alternatives. The lookup reads the registry only and takes no `dataset`:

```json
{"tool":"get_validated_signatures","arguments":{"process":"mTORC1"}}
```

Search by part of a name. `MAPK` finds the KRAS and RAS / RAF / MEK / ERK
processes, which share the readout `PROGENY_MAPK_A`:

```json
{"tool":"get_validated_signatures","arguments":{"query":"MAPK"}}
```

Ask what a familiar set was tested for. `HALLMARK_KRAS_SIGNALING` passed
validation for KRAS but ranked below the readout, so its label is
`passed_not_readout` and the answer names `PROGENY_MAPK_A` instead:

```json
{"tool":"get_validated_signatures","arguments":{"gene_set":"HALLMARK_KRAS_SIGNALING"}}
```

Score a process's readout without its name. `process` replaces `gene_sets` and
`collection`; aliases such as `MEK` also resolve:

```json
{"tool":"get_pathway_scores","arguments":{"process":"RAS / RAF / MEK / ERK","drug":["Trametinib"],"cell_lines":["CVCL_0023"]}}
```

A mixed request reads each set from its own source in one bounded query:

```json
{"tool":"get_pathway_scores","arguments":{"gene_sets":["PROGENY_MAPK_A","HALLMARK_KRAS_SIGNALING"],"drug":["Trametinib"],"cell_lines":["CVCL_0023"]}}
```

| `gene_set` | `score_source` | `validation_status` | Report as |
|---|---|---|---|
| `PROGENY_MAPK_A` | `validated_v02` | `validated_readout` | the validated readout |
| `HALLMARK_KRAS_SIGNALING` | `gold_release` | `passed_not_readout` | exploratory |

The two sources share samples, keys and the cell-line join, but their values
are not interchangeable. Never compare scores across gene sets. Read the
per-set `validation` block and `provenance.score_sources` in the response.

A process with no validated readout scores nothing:

```json
{"tool":"get_pathway_scores","arguments":{"process":"Apoptosis","drug":["Trametinib"],"cell_lines":["CVCL_0023"]}}
```

The answer has `validation_status="no_validated_readout"`, `scored=false`, the
process status (`not_validated`), the best tested set with its arm verdicts,
and caveats. Report that Apoptosis has no validated readout. The server does
not substitute another set, and neither may you. If the user still wants a
score, pass `gene_sets` explicitly and report the result as exploratory.

Read the panel's guide before interpreting:

```json
{"tool":"get_guide","arguments":{"topic":"validated-signatures"}}
```

## Emerald Bay worked calls

First call `list_releases()`. Require an untruncated successful response,
server version at least 0.4.0, and the Emerald entry's `tools`, measurement
lists and table aliases. The tools alone being registered is not enough.
`health()` can help recover a missing version, but cannot replace discovery.
A Tahoe-only, disabled or unauthorized response means stop the Emerald route.
Do not try an unadvertised layer through SQL as a workaround.

Read the Emerald guide before selecting measurements:

```json
{"tool":"get_guide","arguments":{"dataset":"emerald-bay","topic":"establish-the-analysis-contract"}}
```

Discover sample labels, resolve genes and look up the line independently:

```json
{"tool":"search_conditions","arguments":{"dataset":"emerald-bay","limit":20}}
```

```json
{"tool":"resolve_genes","arguments":{"dataset":"emerald-bay","symbols":["TP53","EGFR"]}}
```

```json
{"tool":"list_cell_lines","arguments":{"dataset":"emerald-bay","query":"A549"}}
```

Replace every `<...>` placeholder below with a verified discovery result.
Placeholders are templates, not real identifiers or claims of measured coverage.
Retain `cell_line_internal`, identity uncertainty, complete condition text and
sample. Resolve ambiguous genes before querying; do not choose the first match.
Use a treated sample for the pathway example and a measured profile for numeric
expression. Request unavailable profiles explicitly when checking missingness.

```json
{"tool":"get_drug_info","arguments":{"dataset":"emerald-bay","samples":["<sample>"],"limit":20}}
```

This is condition/sample metadata only. Targets, MOA, approval, structures,
organ/driver filters and scalar dose filters are not Emerald capabilities.
Keep multi-component labels and endpoint controls as separate samples.

Pseudobulk raw counts, with all matched endpoint-control replicates:

```json
{"tool":"get_expression_slice","arguments":{"dataset":"emerald-bay","genes":["<resolved gene>"],"samples":["<sample>"],"cell_lines":["<cell_line_internal>"],"measurement":"raw_counts","include_matched_controls":true,"limit":100}}
```

The same profile and gene, using the full-profile denominator:

```json
{"tool":"get_expression_slice","arguments":{"dataset":"emerald-bay","genes":["<resolved gene>"],"samples":["<sample>"],"cell_lines":["<cell_line_internal>"],"measurement":"cpm","include_matched_controls":true,"limit":100}}
```

Natural-log log1p(CPM), also the expression tool's default measurement:

```json
{"tool":"get_expression_slice","arguments":{"dataset":"emerald-bay","genes":["<resolved gene>"],"samples":["<sample>"],"cell_lines":["<cell_line_internal>"],"measurement":"cpm_log1p","include_matched_controls":true,"limit":100}}
```

Read `expression-measurements-and-missingness` and `conditions-and-controls`.
A gene's CPM must not change when other genes are added to the request. Keep
returned totals, cell counts, population and measured/unavailable status.
Time-zero samples are not endpoint controls. DESeq2 expression and DE are
unsupported; do not call the Tahoe DE tool for this dataset.

Released five-day growth response, without a significance filter:

```json
{"tool":"get_phenotype_scores","arguments":{"dataset":"emerald-bay","samples":["<sample>"],"cell_lines":["<cell_line_internal>"],"phenotypes":["growth_rate_released"],"significant_only":false,"limit":100}}
```

Read `released-growth-response`. `survival` is an accepted source-label alias
for this same value, not clinical survival or Tahoe's phenotype. Preserve the
released value and both population definitions; do not recompute it or invent
p-values. `is_growth_rate_control` is true only for the four endpoint `DMSO_TF`
replicates, never for time zero. `smp_803` (`DMSO_T0`) growth is a
baseline-versus-endpoint contrast flagged `is_time_zero=true`; exclude it from
drug rankings. Other phenotypes and `significant_only=true` are
unsupported.

Discover gene-set names, then retrieve differential scores:

```json
{"tool":"search_gene_sets","arguments":{"dataset":"emerald-bay","query":"APOPTOSIS","limit":20}}
```

```json
{"tool":"get_pathway_scores","arguments":{"dataset":"emerald-bay","gene_sets":["<gene set>"],"samples":["<sample>"],"cell_lines":["<cell_line_internal>"],"limit":100}}
```

Read `differential-vision-scores`. Do not subtract endpoint controls again.
Keep the collection, profile keys, `is_time_zero`, `contrast_kind`,
`is_control_reference` and eligibility status. `contrast_kind` is
`time_zero_vs_endpoint`, `treatment_vs_endpoint` or
`endpoint_control_reference`; filter `is_time_zero=false` for drug rankings.
Eligible `DMSO_T0` profiles have differential scores relative
to the mean matched `DMSO_TF` endpoint controls. Interpret these as
baseline-versus-endpoint contrasts, not drug-treatment effects. Time-zero
profiles can still be absent or below the cell floor; missing, endpoint-reference
and low-cell scores remain unavailable. Absolute VISION is unsupported. The
embedding-distance and perturbation-marker tools are also unsupported here.

When `list_releases()` also shows the validated-signatures panel (server 0.5.0
or later), `search_gene_sets` lists the validated readouts present in the
Emerald vocabulary first, and `process` resolves to the readout:

```json
{"tool":"get_pathway_scores","arguments":{"dataset":"emerald-bay","process":"mTORC1","samples":["<sample>"],"cell_lines":["<cell_line_internal>"],"limit":100}}
```

These are Emerald gold differential scores, never panel scores. The response
adds a per-set `validation` block and a `validation_note`. "Validated" means
validated on Tahoe-100M and DepMap (plus the proprietary verdict), never on
Emerald Bay data; say so beside the result. A custom readout (`PROGENY_`,
`LIT_` or `TIROSH_` names, such as `PROGENY_MAPK_A` for KRAS) is not in the
Emerald vocabulary: its rows have `value_status="gene_set_not_found"` and no
score. Report the readout as unscored on Emerald Bay. Do not replace it with
another set, and never call a substitute validated.

For approved single-cell raw reads or custom aggregates, read the selected
`querying-with-run-sql` and `table-reference` topics and use the examples in
[sql-guidance.md](sql-guidance.md). No unrestricted matrix export is available.

For `pending`, repeat the exact same call, including `dataset`, adding only
`result_handle` from that response. Changed parameters cannot redeem it. If
access disappears, report that fact; do not remove `dataset` or submit a new
Tahoe query. Use `cancel_execution(cancel_handle=...)` to stop an owned query;
cancellation does not take a dataset argument and remains valid after access
is disabled. `send_feedback` is optional and only runs when the user asks.

## Response contract

Check `ok` and `status` first. Dataset results carry the selected `release`;
cancellation is operational and has no dataset release. Discovery lists
releases, rather than choosing one for the user. A data result also carries:

- `provenance` — units, normalization, aggregation and what a zero means.
- `manifest` — tool, canonical arguments, release and server version, so a call
  can be replayed and attributed.
- `truncated` and `truncation_reasons` — `complete` is true only when nothing was
  trimmed.
- With the validated-signatures panel visible, Tahoe pathway rows add
  `score_source` and `validation_status`, and the response adds a per-set
  `validation` block and `provenance.score_sources`; Emerald pathway responses
  add the `validation` block only.
- `pending` — the query outran the submit wait. Call the **same** tool again with
  the **same** arguments and `result_handle` set to the pending response's
  handle; do not resubmit. A handle is bound to the tool, release and arguments
  that produced it, so a handle from another tool, another release or another
  account reads as `not_found`.

Envelope details vary by tool and server version. Older Tahoe condition/gene
responses can report `release` and arguments without a `manifest`. Preserve
all returned provenance; do not infer a dataset from a default health release.

## Errors worth recognizing

| `error_type` | Meaning |
|---|---|
| `bad_request` | An argument is invalid or the dataset does not support that analysis/filter. Do not silently drop the filter or switch datasets. |
| `not_found` | The dataset is unavailable to this account, the named object/handle is unavailable, or the validated-signatures panel is off for this account. Recheck discovery; never remove the Emerald selector to retry. |
| `rate_limited` | Too many calls; wait and retry. |
| `too_large` | The request exceeds a bound; narrow it. |
| `missing_identity` | Sign in through the connector, then retry. |
| `table_not_allowed` | A `run_sql` statement named a table that is not approved. |
| `filter_required` | A `run_sql` statement read a large table without a literal key filter. |
| `query_too_costly` | A `run_sql` statement used a cross join, an unqualified join, or too many tables. |
| `function_not_allowed` | A `run_sql` statement used a refused function or table source. |

A failure is `ok=false`. Use its `error_type` and message to explain the failure;
never treat failed or pending results as measurements. A
truncated success is `ok=true` with `truncated=true`: report it as partial, never
as complete.

## Guide topics

`get_guide(topic=...)` accepts a topic id and returns just that section; the
response lists the available `topics` and the `guide_version`. Emerald requires
`dataset="emerald-bay"` on every guide call. Read the relevant
section before drawing a conclusion. While the validated-signatures panel is
visible, either guide also lists the `validated-signatures` topic.

Use `references/data-catalog.md` to select the server guide topic for each
scientific layer, and read that topic and result provenance before interpreting
a value. Verify the current topic list rather than assuming an older guide
covers a newly advertised tool.

## SQL

A bounded tool first. When no bounded tool fits a join, an aggregate or a table
they do not expose, use `run_sql(statement, max_rows)` — one read-only query over
the approved tables, guarded server-side. The tables, keys, joins, pitfalls and
query rules are in `references/sql-guidance.md`.
