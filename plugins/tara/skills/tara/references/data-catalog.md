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

## Scientific reading map

Read the relevant `get_guide(topic=...)` section and the result's provenance
before interpreting a value. Read `get_guide(topic="table-reference")` before
SQL: it supplies the current columns, grain, identifiers and units. These
summaries are interpretation safeguards, not a replacement table inventory.

| Scientific layer | Server guide topic | Essential distinction |
|---|---|---|
| Expression | `expression-grain-and-measurement` | Absolute sample/line aggregate, not fold change or a single-cell distribution. |
| DE | `differential-expression` | Released contrast with synthetic pseudoreplicates and optimistic uncertainty. |
| Pathways | `pathway-scores` | Differential VISION, already vehicle-subtracted; gene-set choice changes the question. |
| Markers | `response-markers` | Classifier importance, not direction, fold change or causal mechanism. |
| Phenotypes | `phenotype-readouts` | Select the phenotype before interpreting the score, direction or significance. |
| Embeddings | `embedding-distances` | Model-dependent distance from matched vehicle, without direction. |

### Expression and DE

`get_expression_slice` serves summed single-cell UMI counts per sample and line,
or `cpm_log1p = ln(1 + 1e6 * raw_counts / total_counts)` for that aggregate's
library size. These are measurements. A difference of log-normalized values
is not automatically a log2 fold change. Several aggregates can share an arm;
their row count and `n_cells` do not establish independent biological n.
Matched expression controls have dose zero at the same gene, plate and line.

`get_differential_expression` serves PyDESeq2 contrasts against pooled
same-plate, same-line vehicle wells. Its three synthetic multinomial
pseudoreplicates do not estimate between-well biological variance: `lfcSE`,
`pvalue` and `padj` are optimistic. An interval derived from that SE inherits
the limitation. Unshrunk fold changes can be extreme at low counts; assess
effect size and consistency rather than tiny p-values. BH adjustment is within
one contrast, not across plates, drugs or doses. Do not recompute it on a
selected gene subset. NULL p-values mean untested, not no effect. Other public
DE releases may use different estimation methods; shared gene labels do not
make their statistics interchangeable.

### Pathways and gene-set definitions

`get_pathway_scores` returns differential VISION scores, already relative to
matched vehicle. They are dimensionless, have no provided p-value/FDR, and must
not have another control subtracted. An absolute signature score means
pre-subtraction, not absolute molecular abundance; score magnitudes are not
interchangeable across different gene sets.

Use `search_gene_sets` to discover the selected source's names. Related
HALLMARK, REACTOME or GOBP sets, and `_UP`/`_DOWN` halves, are not substitutes
for one another. A name does not establish gene membership or scoring version.
Verify a released definition when the claim depends on membership; otherwise
state the definition is unverified. For broad biological questions, explain
the chosen set and whether a defensible alternate set changes the conclusion.
Aggregate within each line before across lines, preserving dose and plate.

Use a released differential score as-is. Reconstructing it from an absolute
table requires compatible scoring builds, definitions, sample keys and matched
controls plus a numeric check; a successful join alone is insufficient. A NULL
score or an unscored sample/set is unavailable, not zero.

### Phenotypes and classifier readouts

`get_phenotype_scores` returns one row per drug, line, dose, plate and phenotype.
Preserve repeated plates as separate rows and distinguish cell/sample counts
from biological replication. The current tool's provenance distinguishes:

- `survival`: relative depletion against other pooled lines, not absolute
  viability. Uniform killing can score near zero; negative values do not alone
  establish an absolute viability effect.
- `g1_arrest`, `s_arrest`, `g2m_arrest`: phase-specific log2 odds ratios against
  matched vehicle; positive means phase enrichment.
- `gini`: a permutation-referenced cluster-occupancy Z-score.
- `augur`: a composite of six perturbation metrics, not a pure classifier AUC.
  A separate source's `auc` column must not be treated as this same statistic.

The FDR family is one phenotype across the panel. Gini and Augur have no FDR;
NULL significance fields mean no such statistic, not zero or “not significant.”
`significant_only` is refused for those readouts. `significant=false` is not
evidence of no effect. `get_perturbation_markers` ranks classifier features;
importance has no direction, and an absent gene may not have been modeled.

### Embeddings and identity

`get_embedding_distance` compares treatment and vehicle centroids matched by
plate and line. Current provenance describes Tx1-3B, 2,560 dimensions, vectors
scaled by `1/sqrt(2560)`, and cosine/L2 distances. Distances have no direction
and their scale is model-dependent. Preserve contributing cell counts and
low-cell-count warnings; centroid counts are not biological n. Compare within
the same line and matched context. The named tool returns scalar distances;
approved SQL may expose plate-level centroid vectors. Per-cell vectors remain
outside this service.

Named tools translate line identifiers to public ids and names. SQL can expose
source keys: resolve them through the advertised metadata, check uniqueness
and join row counts, and present public identity. Driver-gene membership alone
does not establish a specific variant or functional state; verify annotations
and stratum coverage before making a genotype claim.

## Coverage traps

- Presence in a compound library is not coverage in the release. Confirm an arm
  exists with `search_conditions` before a question or request assumes it.
- Panel drug names appear as free base and as salt form. Count and ranking
  questions over drugs must dedupe to the parent or active moiety, or one drug
  counts twice and top-N rankings shift. If parent identity cannot be established
  from released annotations, report label counts and that limitation.
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
