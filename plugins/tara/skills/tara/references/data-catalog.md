# The served Tahoe-100M dataset

What this server serves, and the traps to avoid. This is not an inventory:
confirm what a release contains with `list_releases`, `search_conditions`,
`list_cell_lines` and `resolve_genes`, and read `get_guide(...)` for the
server's own account of conditions and controls, genes, expression grain,
differential expression and table semantics (its topic list is in the response).
`list_releases()` names the release; every result carries it, so a figure can be
pinned. A newer release is a source change: re-establish coverage.

## What is served

One bounded, read-only slice of the public **Tahoe-100M** release, reached only
through this server's tools. There is no direct table or file access; the only
client-supplied query is one guarded, read-only `run_sql` statement over the
approved tables. Scientific data tools are read-only and run as the service's
own read identity, so the release is the same for every caller. The cancellation
and optional-feedback controls affect only the caller's operational state.
Responses are bounded to a fixed byte ceiling: a truncated response says so,
and narrowing the request is the only way to see more.

## Registered release tables

The public tools use the registered Delta-table routes for the approved
Tahoe-100M release. They query in place rather than downloading retained release
files. The bounded expression tool uses `pseudobulk_expression`; single-cell
SQL uses `single_cell_expression`, `obs` and `gene_metadata`. Other bounded
tools use the approved DE, pathway, phenotype and metadata tables.

Use `list_releases` and the server's table reference to establish the selected
release and routes. The plugin does not choose an arbitrary newest dataset or
reference release: a newer release is a scientific source change, so re-establish
population, measurement and coverage. External reference datasets are outside
this service's approved scope. Table names and a release label do not pin a
Delta transaction version; retain source-version evidence when available.

## Scientific reading map

Read the relevant `get_guide(topic=...)` section and the result's provenance
before interpreting a value. Read `get_guide(topic="table-reference")` before
SQL: it supplies the current columns, grain, identifiers and units. These
summaries are interpretation safeguards, not a replacement table inventory.

| Scientific layer | Server guide topic | Essential distinction |
|---|---|---|
| `get_expression_slice` | `expression-grain-and-measurement` | Pseudobulk measurement, not a single-cell distribution. |
| Single-cell SQL | `table-reference` | Sparse per-cell counts with verified cell and gene axes. |
| DE | `differential-expression` | Released contrast with synthetic pseudoreplicates. |
| Pathways | `pathway-scores` | Differential VISION, already vehicle-subtracted. |
| Markers | `response-markers` | Classifier importance, not direction, fold change or causal mechanism. |
| Phenotypes | `phenotype-readouts` | Select the phenotype before interpreting the score, direction or significance. |
| Embeddings | `embedding-distances` | Plate-preserving centroids and the tool's reported distance metrics. |

### Expression routes

`get_expression_slice` returns one pseudobulk row per gene, sample and line,
with drug, dose, plate and cell counts. `raw_counts` are summed UMI counts and
`cpm_log1p = ln(1 + 1e6 * raw_counts / total_counts)`; this is expression, not
fold change.

`run_sql` can also query `single_cell_expression`: sparse rows keyed by
`cell_joinid` and `gene_joinid`, with raw counts in `value` and condition keys
`cell_line` and `sample`. Join the cell axis to `obs.soma_joinid` and the gene
axis to `gene_metadata`. Resolve the line and sample from metadata, then push
both filters onto expression. Use pseudobulk when the question needs aggregate
expression; it cannot replace an explicitly single-cell analysis. Sparse
omissions mean zero only inside verified measured cell x gene axes; no profile
or an unmeasured gene is unavailable, not zero.

### Differential expression

`get_differential_expression` serves treatment-versus-pooled same-plate,
same-line DMSO_TF results. PyDESeq2 uses three synthetic multinomial
pseudoreplicates per arm; they do not estimate between-well biological variance.
`n_cells_trt` and `n_cells_ctrl` count contributing cells, not independent
replicates. Other public DE releases can use different methods; do not conflate
them with these PyDESeq2 results. Establish the selected source's design,
statistics and missingness from the guide and provenance before interpreting it.

### Pathway scores

`get_pathway_scores` returns differential VISION scores. `cell_id` identifies
a pseudobulk sample, not a single cell. Released comments describe the score
as sample signature activity minus the mean of plate- and line-matched vehicle
samples, not a median/IQR statistic or expression fold change. Scores carry no
p-value. Averaging drug-induced changes does not estimate untreated baseline
pathway activity. Use the differential score as-is; never subtract a vehicle,
control or baseline again.

Use the selected relation's vocabulary: absolute and differential scores can
cover different sets. Use `search_gene_sets` for the served names. Do not
substitute a similarly named or signed set without verifying its definition.
The original Tahoe scoring gene-set file is not recovered, so an external
MSigDB definition alone does not establish identical membership. Confirm score
semantics through the server guide and result provenance.

### Phenotype scores

`get_phenotype_scores` preserves drug, line, dose, plate, phenotype and cell
counts. Score semantics differ per phenotype; verify the selected table's
comments, grain, controls and direction before interpreting a value. Survival
uses relative-abundance odds ratios against matched vehicle, phase-arrest
scores describe phase shifts, and Gini measures response specificity as a
Z-score. For Augur and Gini, `p_adj_fdr` and `significant` are NULL by construction;
absent is not “not significant.” The public tool refuses `significant_only`
for these readouts.

For the exact Augur statistic, read the served `phenotype-readouts` guide and
provenance; a shared name across relations does not establish identical score
semantics. Classifier feature rankings use `get_perturbation_markers`; preserve
their reported measurement rather than treating them as expression contrasts.

### Embeddings and identity

The Tx1-3B vector has 2,560 dimensions and uses `raw / sqrt(2560)` normalization.
Centroids are means per plate, line and treatment condition, with contributing
cell counts; preserve plate-matched controls and do not treat centroids as
individual cells or replicates. `get_embedding_distance` returns distances
from matched vehicle; read its guide and provenance for the reported metrics.
The tool returns scalars; approved SQL can expose plate-level centroid vectors.
Per-cell vectors are outside this public service.

Resolve source line keys through release metadata. Verify the selected key's
uniqueness, annotation coverage and release membership before joining; preserve
public ids and names in the result.

## Coverage traps

- Presence in a compound library is not coverage in the release. Confirm an arm
  exists with `search_conditions` before a question or request assumes it.
- Panel drug names appear as free base and as salt form. Count and ranking
  questions over drugs must dedupe to the parent or active moiety, or one drug
  counts twice and top-N rankings shift.
- Drug labels are case-sensitive and may be lowercase or carry a salt suffix.
  Confirm them with `search_conditions(query=...)`; use `list_cell_lines` for
  line identifiers. Use the returned vocabulary verbatim.
- The panel is cancer lines plus one immortalized normal line; exclude or note
  it before a pan-cancer claim. The same caution applies to genotype and lineage
  strata, where n can be thin.
- A substring match on the vehicle label also selects real treatments whose
  labels contain that substring as a salt. Match the vehicle as the exact label,
  not a substring.
- A missing row is not zero. Sparse omissions mean zero only inside the verified
  measured gene and condition axes; an unmeasured gene or an absent condition is
  unavailable, not zero.
- Coverage facts are release-specific, so re-check them when the release changes.

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
3 doses, vehicle `DMSO_TF`), one 50-line cell panel, 14 plates. There is no file
or table browsing; the only client-supplied query is a guarded `run_sql`
statement, and a table outside the approved set is refused. Not available, so do
not search for it here:
other Tahoe screens or unreleased datasets; clinical or adverse-event data;
proprietary external reference panels (dependency, viability or signature
databases) joined to this release; unreleased compound annotations beyond the
released drug metadata; per-cell embeddings (public in the Hugging Face release,
not through these tools). Plate-level centroid vectors and source identity
columns may be queried through approved SQL; named tools return scalar
distances and public line identities. If a
question needs one of these, say so and stop; do not substitute a different
population, measurement or dataset silently.
