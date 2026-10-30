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
| Interpreting a validated readout (panel visible) | `validated-signatures` | `validated-signatures` |
| Interpreting phenotype | `phenotype-readouts` | `released-growth-response` |
| Preparing reproducible output and citation | `reporting-standards`, `reproducible-output`, `citation-and-provenance` | `provenance-and-attribution` |
| Writing bounded SQL | `querying-with-run-sql`, `table-reference` | `querying-with-run-sql`, `table-reference` |

Read relevant sections before interpreting any value. A shared tool name does
not establish shared units, controls, populations or uncertainty. Never reuse
Tahoe's guide version as evidence for Emerald. If methods or identity remain
uncertain, state the uncertainty instead of inventing a convention. Keep the
runtime guidance in the analysis session; do not redistribute it with the plugin.

## Validated signatures

Apply these rules whenever a pathway or program answer uses the panel. Read the
`validated-signatures` topic and the lookup's `caveats` for the details.

1. **Use the readout.** Report every other set as exploratory, including a set
   that passed validation but is not the readout (`passed_not_readout`). Only
   `validated_v02` rows carry the validated label; `gold_release` rows are
   exploratory. A `source_authority` readout (the metabolic Hallmarks) was
   released from its source and never tested; say so.
2. **No readout, no substitute.** A process with no validated readout
   (`no_validated_readout`, process status `not_validated` or `not_released`)
   has no validated answer. Say that first. Score another set only when the
   user asks, and label it exploratory.
3. **A moving readout does not show target engagement.** It shows that the
   process's transcriptional program moved. Say so whenever you name a drug's
   target or mechanism.
4. **Respect the direction class.** `direction` is the expected sign under the
   process's therapeutic drugs: `down`, `up`, `conditional` (read `condition`)
   or `complex` (no single expected sign). Do not call a `complex` readout's
   change "on-mechanism" from its sign alone.
5. **Three scores are inverted.** For `CHICAS_RB1_TARGETS_SENESCENT`,
   `IGARASHI_ATF4_TARGETS` and `EHLERS_ANEUPLOIDY`, a higher score means less
   of the process. Read `score_direction_note` and state the direction in
   process terms, not score terms.
6. **Weigh circularity.** `circularity` grades, per arm, the risk that the
   validation is circular; a flag marks a borderline readout. Treat flagged
   evidence as weaker and say why.
7. **Check proliferation.** Scores correlate with proliferation to different
   degrees (`proliferation_r`). The served scores carry no proliferation
   correction. Do not residualise or adjust them yourself, and do not present
   an adjusted value as the release's. Before attributing a change to the
   process, check whether it tracks proliferation, and report that caveat.
8. **Never compare scores across gene sets.** Compare one set across
   conditions. Do not rank processes by score size, and do not treat a
   `validated_v02` value and a `gold_release` value as interchangeable.
9. **Caveat DepMap-only readouts for drug claims.** Read `arms` before a drug
   claim. Where only DepMap genetics supports a readout, the Tahoe-100M arm was
   not testable and no drug class was shown to move it. A drug-effect claim
   then rests on genetic evidence alone; say so in the answer.
10. **Report arms by their labels.** The proprietary arm is a verdict only; do
    not ask for, infer or invent its values, drugs or counts. Pending licence
    review, the DepMap arm is a verdict plus the tested genetic contrast. Only
    the Tahoe-100M arm carries values.
11. **Keep the Emerald scope.** On Emerald Bay a label means validated on
    Tahoe-100M and DepMap (plus the proprietary verdict), never on Emerald
    data; the scores are Emerald gold values. Custom readouts return
    `gene_set_not_found` there and are reported as unscored, never replaced.
