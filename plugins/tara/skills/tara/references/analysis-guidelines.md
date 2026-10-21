# Reading the selected dataset's scientific guidance

Scientific methods live in `get_guide`, not in a second plugin-owned guide.
Discover the dataset first. For Tahoe, start with
`get_guide(topic="establish-the-analysis-contract")`. For Emerald, use
`get_guide(dataset="emerald-bay", topic="establish-the-analysis-contract")`
only after discovery advertises it. Keep the returned `guide_version`, verify
the topic list, and pass the same dataset selector on subsequent guide calls.

| Before | Tahoe-100M topic | Emerald Bay topic |
|---|---|---|
| Planning the analysis | `establish-the-analysis-contract` | `establish-the-analysis-contract` |
| Resolving genes and cell lines | `genes`, `coverage-traps` | `gene-and-cell-line-identity` |
| Selecting controls and joins | `verify-semantics-and-coverage`, `conditions-and-controls` | `conditions-and-controls` |
| Interpreting expression | `expression-grain-and-measurement` | `expression-measurements-and-missingness` |
| Choosing statistical units | `statistical-discipline` | `drug-metadata-and-statistical-discipline` |
| Interpreting released DE | `differential-expression` | Unsupported |
| Interpreting pathways | `pathway-scores` | `differential-vision-scores` |
| Interpreting phenotype | `phenotype-readouts` | `released-growth-response` |
| Preparing reproducible output and citation | `reporting-standards`, `reproducible-output`, `citation-and-provenance` | `provenance-and-attribution` |
| Writing bounded SQL | `querying-with-run-sql`, `table-reference` | `querying-with-run-sql`, `table-reference` |

Read relevant sections before interpreting any value. A shared tool name does
not establish shared units, controls, populations or uncertainty. Never reuse
Tahoe's guide version as evidence for Emerald. If methods or identity remain
uncertain, state the uncertainty instead of inventing a convention. Keep the
runtime guidance in the analysis session; do not redistribute it with the plugin.
