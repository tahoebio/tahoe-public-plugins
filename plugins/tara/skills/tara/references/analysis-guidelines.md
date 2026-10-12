# Scientific analysis guidelines

Use these criteria when selecting what to retrieve and when interpreting a
result from this server.

## Establish the analysis contract

Before a substantive call, state the endpoint, comparison, unit of analysis,
population and required covariates. Decide whether the question needs a
pseudobulk aggregate, a per-arm summary, or a per-cell-line comparison. Use the
smallest sufficient slice; the 50-line panel is not a reference cohort.

## Verify semantics and coverage

- Confirm release, gene label, condition identity, control arm, value direction,
  and whether a value is an absolute measurement or a treatment-versus-control
  contrast.
- Check compound and cell-line coverage in the served release with
  `search_conditions`, not only in library metadata.
- Resolve compound synonyms through the release's own labels. Preserve
  parent/salt distinctions when relevant.
- Resolve gene identifiers with `resolve_genes` before joining across layers.
- Before aggregation, verify that joins preserve the intended independent unit;
  compare unique units and row counts before and after the join.
- Preserve dose, unit, plate, cell line, sample, replicate count and analysis
  grain.
- Report missingness and the number of independent biological units, not only
  row or aggregate count.
- Do not treat aggregates from the same sample as independent biological
  replicates.

## Statistical discipline

- Match controls by the design encoded in the release, commonly plate and cell
  line; do not pool controls merely to increase n.
- Across the panel the independent unit is the cell line; within one line it is
  the plate-matched sample, often too few for an interval (report the difference
  with treated and control counts). Cells, wells and pseudo-replicates within a
  sample are not independent replicates.
- Distinguish exploratory ranking from confirmatory inference. The pre-specified
  estimate is the result; an adjustment invented after seeing the data is
  exploratory and is labelled so.
- Report every estimate as an effect size with a 95% interval and n, or, where
  the independent units are too few for an interval, the difference with its
  unit counts. Summarise
  across conditions with a pooled estimate and interval, not with a count of
  significant conditions.
- Account for multiple testing when selecting across genes, compounds or strata.
  Nominal p-values and BH within a pre-specified family may be reported; they
  never carry the headline and never support a claim of no effect.
- No post-hoc adjustment gates: do not residualise a score on other gene sets,
  on a hallmark median, on cell number or on any proxy of the outcome, and do
  not report q-values derived from such adjustments. A null after adjusting for a
  proxy of the outcome is uninterpretable.
- Do not use panels of related pathways as comparator groups to argue
  specificity; sets that share genes are correlated by construction.
- Make no definitive claims about in vivo versus in vitro translatability from
  one study; report cross-arm agreement on shared units descriptively, and say
  when doses are matched by rank rather than pharmacologically.
- Avoid genotype- or lineage-stratified conclusions when the number of lines or
  perturbations is thin; report n explicitly in the sentence that makes the
  claim.
- Do not infer mechanism directly from pathway enrichment, transcriptional
  similarity or target annotations alone.
- Pseudobulk or aggregate results and single-cell state distributions answer
  different questions.

## Measurements versus treatment contrasts

- A served value is an expression measurement -- an absolute pseudobulk
  aggregate -- unless the release publishes it as a contrast. Read the
  `provenance` block to establish which it is before using it.
- A treatment-versus-control contrast is computed by the analyst from the
  aggregates and the matched control rows. State the definition in the Methods
  and in every figure footnote, for example: "Delta = treated aggregate minus the
  matched control aggregate, computed here; the served values are absolute and
  were not pre-subtracted."
- Do not subtract a vehicle, control or baseline value from a served value that
  is already a contrast, and do not re-centre a contrast on control groups.
- Before analysis, print the `provenance` block and run one numeric check that
  confirms the semantics; keep the check and its output in the analysis record.

## Reporting standards

- Separate Observed, Interpretation, and Assumptions and limits; every number in
  the text is traceable to an exported table column.
- Figures and tables are numbered and each has a caption. Cite them inline
  ("see Fig. 2b", "Table 3"); never describe a figure without a reference.
- Every figure footnote states the value definition, the release, the cohort,
  the arm, the unit of replication and what the interval is.
- Lead with the bottom line as effect sizes and intervals; export the plotted
  matrix and the per-condition rows as CSV beside each figure.
- Deliverables carry no service URLs, identities, handles or third-party names.
  Provenance for a deliverable lives in a separate record (see Reproducible
  output).

## Reproducible output

Retain exact arguments, filters, parameter values, release and access date, row
counts, filtering decisions and software versions. Keep downloaded data and
derived tables outside git-tracked paths unless the repository explicitly
permits a small non-sensitive artifact. Never commit raw Tahoe data.

In the final explanation, separate:

1. directly observed results;
2. statistical or biological interpretation;
3. assumptions and unresolved limitations.
