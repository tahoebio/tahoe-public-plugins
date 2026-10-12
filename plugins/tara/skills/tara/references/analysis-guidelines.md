# Scientific analysis guidelines

Use these criteria when selecting a source and interpreting its results.

Establish the measurement and row grain from the server guide before choosing
a route. `get_expression_slice` returns pseudobulk measurements; `run_sql` over
`single_cell_expression` returns sparse per-cell raw counts. Pseudobulk is not
a substitute for a question requiring single-cell distributions.

## Establish the analysis contract

Before a substantive retrieval or SQL query, state the endpoint, comparison, unit of analysis, population,
and required covariates. Decide whether the question needs single-cell distributions, pseudobulk
expression, differential expression, pathway scores, phenotypes, compound identity, or embedding
distances. Use the smallest sufficient source; the Tahoe screen panel is not
the default population for a question about a broader reference panel.

## Verify semantics and coverage

- Confirm release/version, schema, row grain, controls, score direction, and whether values are
  absolute measurements or treatment-versus-control contrasts.
- Check compound and cell-line coverage in the selected release, not only in library metadata.
- Resolve compound synonyms through registered identity data. Preserve parent/salt distinctions
  when relevant.
- Resolve cell-line codes through release metadata before joining across layers.
- Before aggregation, verify that joins preserve the intended independent unit; compare unique
  units and row counts before and after the join.
- Preserve dose, unit, plate, cell line, sample, replicate count, and analysis grain.
- Report missingness and the number of independent biological units, not only row or cell count.
- Do not treat cells from the same sample as independent biological replicates.

## Statistical discipline

- Match controls by the design encoded in the release, commonly plate and cell line; do not pool
  controls merely to increase n.
- The independent biological unit, usually the cell line, is the unit of replication. Cells,
  wells, tumours and pseudo-replicates within it are not independent replicates.
- Distinguish exploratory ranking from confirmatory inference. The pre-specified estimate is
  the result; an adjustment invented after seeing the data is exploratory and is labelled so.
- Report every estimate as an effect size with a 95% interval and n. Summarise across
  conditions with a pooled estimate and interval, not with a count of significant conditions.
- Account for multiple testing when selecting across genes, pathways, compounds, or strata.
  Nominal p-values and BH within a pre-specified family may be reported; they never carry the
  headline and never support a claim of no effect.
- No post-hoc adjustment gates: do not residualise a score on other gene sets, on a hallmark
  median, on cell number or on any proxy of the outcome, and do not report q-values derived
  from such adjustments. A null after adjusting for a proxy of the outcome is uninterpretable.
- Do not use panels of related pathways as comparator groups to argue specificity; sets that
  share genes are correlated by construction.
- Make no definitive claims about in vivo versus in vitro translatability from one study;
  report cross-arm agreement on shared units descriptively, and say when doses are matched by
  rank rather than pharmacologically.
- Calculations made outside a release model (for example empirical compositions against
  vehicle samples) are labelled descriptive and are not reported in partner-facing output.
- Avoid genotype- or lineage-stratified conclusions when the number of lines or perturbations is
  thin; report n explicitly in the sentence that makes the claim.
- Do not infer mechanism directly from pathway enrichment, transcriptional similarity, or target
  annotations alone.
- Pseudobulk/aggregate results and single-cell state distributions answer different questions.

## Treatment contrasts versus absolute scores

- A release differential table (for example a differential VISION table) already holds
  treatment minus the matched control, computed by the release pipeline. Its values are
  used as-is: never subtract a vehicle, control, DMSO or baseline value from them again, and
  never re-centre them on control groups.
- Absolute control scores, where a release publishes them, serve an untreated-baseline view
  only. A reconstructed absolute treated score is differential plus the matched control mean
  and is labelled "reconstructed absolute".
- Before analysis, read the relevant server guide and result provenance and run one numeric check
  that confirms the semantics; keep the check and its output in the analysis record.
- State the definition in the Methods and in every figure footnote, for example:
  "Δ = release differential score (treated minus matched control, computed by the release
  pipeline), used as-is; no further control subtraction was applied."

## Reporting standards

- Separate Observed, Interpretation, and Assumptions and limits; every number in the text is
  traceable to an exported table column.
- Figures and tables are numbered and each has a caption. Cite them inline ("see Fig. 2b",
  "Table 3"); never describe a figure without a reference.
- Every figure footnote states the score definition, the run or release, the cohort, the arm,
  the unit of replication and what the interval is.
- Lead with the bottom line as effect sizes and intervals; export the plotted matrix and the
  per-condition rows as CSV beside each figure.
- Partner-facing deliverables carry no service URLs, identities, handles or other partners' names.
  Provenance for a partner-facing report lives in a separate analysis record (see Reproducible output).

## Reproducible output

Retain the served source, exact SQL or tool arguments, parameter values, release dates, row counts, filtering decisions, and
software versions. Keep downloaded data and derived tables outside git-tracked paths unless the
repository explicitly permits a small non-sensitive artifact. Never commit raw Tahoe data.

In the final explanation, separate:

1. directly observed results;
2. statistical or biological interpretation;
3. assumptions and unresolved limitations.
