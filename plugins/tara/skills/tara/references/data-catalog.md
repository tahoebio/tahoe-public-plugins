# Finding the served data catalog

Call `list_releases()` and select the requested dataset entry. Its aliases and
capabilities are authoritative for this account. Server 0.4.0 adds optional
Emerald Bay support; that version alone does not make Emerald available. Old
Tahoe-only responses remain valid for Tahoe, but cannot establish Emerald
coverage. Never substitute one release for another.

The plugin does not ship table schemas. Read the selected `get_guide` and retain
its `guide_version`; see [analysis-guidelines.md](analysis-guidelines.md) for
dataset-specific topic IDs.

| Need | Tahoe-100M guide topic | Emerald Bay guide topic |
|---|---|---|
| Scope | `what-is-served`, `establish-the-release` | `establish-the-analysis-contract` |
| Conditions and controls | `conditions-and-controls` | `conditions-and-controls` |
| Gene / line identity and coverage | `genes`, `coverage-traps` | `gene-and-cell-line-identity` |
| Pseudobulk | `expression-grain-and-measurement` | `expression-measurements-and-missingness` |
| Single-cell raw count access | `table-reference`, `querying-with-run-sql` | `expression-measurements-and-missingness`, `table-reference`, `querying-with-run-sql` |
| DE | `differential-expression` | Not supported |
| Differential VISION | `pathway-scores` | `differential-vision-scores` |
| Validated readouts (panel visible) | `validated-signatures` | `validated-signatures` |
| Phenotype | `phenotype-readouts` | `released-growth-response` |
| Embeddings / classifier markers | `embedding-distances`, `response-markers` | Not supported |
| Attribution | `citation-and-provenance` | `provenance-and-attribution` |

For Tahoe, discover lines with `list_cell_lines(organ=...)` or
`list_cell_lines(query=...)`; prefer its returned Cellosaurus `cell_line` for
data filters. Names, `cell_name` and `depmap_id` support cross-reference.

For Emerald, pass `dataset="emerald-bay"` to discovery and data tools. Keep the
returned `cell_line_internal` key, readable names/cross-references and identity
status. Emerald does not supply organ or driver annotations. A mapped name is
not externally confirmed merely because a cross-reference exists. Resolve
sample labels with `search_conditions`; sample plus line identifies a profile.
Keep complete combination labels and separate endpoint-control replicates.
`get_drug_info` supplies condition metadata, not targets/MOA/approval data.

Resolve genes before expression. Preserve ambiguous matches, measured-axis
membership and unavailable groups; vocabulary membership is not measurement.
Use `get_expression_slice` for pseudobulk raw counts, CPM or natural-log
log1p(CPM). The denominator covers the whole profile, independent of the gene
subset. DESeq2 normalization and differential expression are not Emerald
capabilities. For per-cell raw counts, use a bounded `run_sql` aggregate over
the selected dataset's advertised alias. No full matrix export is served.

Use released growth values with their phenotype population and expression
availability flags. They are five-day in-vitro responses, not clinical survival
or Tahoe survival statistics. Differential VISION is already control-subtracted;
eligible time-zero profiles carry baseline-versus-endpoint scores, not
drug-treatment effects. Reference-only, low-cell or absent profiles must not
become zero scores; time-zero identity alone is not an exclusion.
Never infer complete coverage from a truncated response. Read the guide and
result provenance for the current populations, controls and definitions.

## Validated signature panel

- **What it is.** The Tahoe Signatures panel, release `tahoe-signatures/v02`,
  names one validated readout per cancer process and records its evidence,
  caveats and tested alternatives. It is not a dataset.
- **Availability.** Server 0.5.0 or later. The panel is visible only when the
  Tahoe-100M `list_releases` entry carries `validated_signatures`, which
  reports the release, process and signature counts, tools, scope and arm
  labels. Absent means off for this account: no gene set is validated.
- **Tahoe-100M.** The released signatures (readouts and composite components)
  are scored from the panel's own table (`score_source="validated_v02"`): the
  treated pseudobulk VISION score minus the mean of same-line vehicle samples
  on the same plate. A NULL score means no vehicle on that plate, not zero.
  Every other set reads the released VISION store (`gold_release`).
- **Emerald Bay.** Labels only. Scores are Emerald gold differential values;
  custom readouts (`PROGENY_`, `LIT_`, `TIROSH_`) have none there.
- **Validation.** Three arms, by label: DepMap genetics, Tahoe-100M drug
  classes, and Tahoe proprietary single-cell drug data (unpublished, a verdict
  only). Read the rule from `validation_rule` in the lookup.
- **Not served.** Gene-set member lists, panel scores through `run_sql`, and
  DepMap statistics.

Attribution (pending review). Cite the panel's scores as computed by Tahoe Bio
with VISION (DeTomaso et al. 2019, Nat Commun 10:4376) on Tahoe-100M, whose
source data are CC0. Gene-set names come from MSigDB (CC BY 4.0; Subramanian
et al. 2005, Liberzon et al. 2015), from PROGENy-derived bins (Schubert et al.
2018; Apache-2.0; modified by Tahoe Bio and not endorsed by the PROGENy
authors) and from published studies; cite each set's source as the guide
gives it.
