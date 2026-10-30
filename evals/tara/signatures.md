# S1–S8 — Validated signature readouts

Eight prompts for the validated-signatures panel (release
`tahoe-signatures/v02`). S1–S6 use Tahoe-100M; S7 and S8 use Emerald Bay.
Every criterion below comes from the public registry, as served by
`get_validated_signatures`, or from public Tahoe-100M and Emerald Bay data.
These cases are prepared only: no real host session has run them.

## Preconditions and recording

- Server 0.5.0 or later, and `list_releases()` shows `validated_signatures` on
  the Tahoe-100M entry for the signed-in account. Record its `release`,
  `registry_sha256` and `guide_version`. S7 and S8 also need Emerald Bay to be
  advertised to the account.
- If the panel is not visible, S1–S5, S7 and S8 are **BLOCKED**, not passed.
  S6 runs either way.
- One fresh session per prompt per host. Record the run in
  [run-log.template.md](run-log.template.md) and add the panel fields above.
- **Expected values.** No case freezes a number. Where a criterion depends on a
  value (a direction for one drug, or vocabulary membership on Emerald), the
  case says **needs an independent expected value**. Derive it from the public
  source before seeing any candidate answer, as
  [emerald-oracle.md](emerald-oracle.md) describes for Emerald. Never use the
  candidate's output as the expected value. Until that value exists, grade the
  dependent criterion **BLOCKED**.

Shared hard criteria for S1–S5, S7 and S8, in addition to the
[rubric](rubric.md):

- The answer names the gene set behind every number, with its `score_source`
  (Tahoe) and `validation_status`.
- Only a `validated_readout` set is called validated. Every other set is
  called exploratory.
- No answer claims target engagement from a moving readout.
- No answer compares scores across gene sets or ranks processes by score size.
- A proprietary-arm result is reported as a verdict only. No value, drug or
  count is attributed to it.

## S1 — A MAPK inhibitor uses `PROGENY_MAPK_A`

> In Tahoe-100M, does Trametinib suppress MAPK pathway activity? Report per
> cell line.

**Expected route.** `list_releases()`; `get_validated_signatures(query="MAPK")`
or a process lookup (`RAS / RAF / MEK / ERK`, its aliases `MEK` or `ERK`, or
`KRAS`); `search_conditions(drug="Trametinib")`; then
`get_pathway_scores(process=..., drug=["Trametinib"])` or
`gene_sets=["PROGENY_MAPK_A"]`.

**Hard criteria.**

- The scored set is `PROGENY_MAPK_A`, the registry readout of both
  RAS / RAF / MEK / ERK and KRAS.
- The rows used have `score_source="validated_v02"` and
  `validation_status="validated_readout"`.
- The expected sign is the registry's direction class, `down`. The observed
  direction is reported from the rows, per line, with NULL scores reported as
  missing.
- No other MAPK or KRAS set is presented as the validated readout.

**Soft criteria.** Notes the registry caveat that the readout's circularity
grade is `edge`. Notes that the scores carry no proliferation correction.

**Expected values.** The registry records the direction class `down` and lists
Trametinib among the Tahoe-100M arm's RAF (pan) / MEK / ERK inhibitor class.
That is a class result, not a per-line expectation. Whether Trametinib lowers
the score in most lines **needs an independent expected value** from the public
Tahoe-100M panel scores.

## S2 — Apoptosis has no validated readout

> In Tahoe-100M, how does Trametinib change apoptosis pathway activity in A549?

**Expected route.** `list_releases()`;
`get_validated_signatures(process="Apoptosis")` or
`get_pathway_scores(process="Apoptosis", drug=["Trametinib"], cell_lines=["CVCL_0023"])`.

**Hard criteria.**

- The answer states that the panel has no validated Apoptosis readout. The
  process status is `not_validated`, and a `process` request returns
  `validation_status="no_validated_readout"` with nothing scored.
- No set is called a validated apoptosis readout. In particular,
  `TP53_PROAPOPTOTIC_INDUCED` (best tested; the Tahoe-100M and proprietary arms
  are opposite) and `HALLMARK_APOPTOSIS` (`failed_validation`) are not.
- No other process's readout, such as p53, is substituted as an apoptosis
  readout.
- If the agent scores a set anyway, it does so explicitly with `gene_sets`,
  labels the result exploratory and names its `gold_release` source.

**Soft criteria.** Names the best tested set and its arm verdicts.

**Expected values.** None numeric. The process status and labels come from
the registry.

## S3 — `HALLMARK_KRAS_SIGNALING` was tested but is not the readout

> Is HALLMARK_KRAS_SIGNALING a good readout of KRAS pathway activity for drug
> effects in Tahoe-100M?

**Expected route.** `list_releases()`;
`get_validated_signatures(gene_set="HALLMARK_KRAS_SIGNALING")`; optionally
`get_validated_signatures(process="KRAS")`.

**Hard criteria.**

- The answer says the set was tested for KRAS and for RAS / RAF / MEK / ERK,
  passed validation, and is not the readout: its label is
  `passed_not_readout`.
- It names `PROGENY_MAPK_A` as the validated readout to prefer.
- Any score it reports for `HALLMARK_KRAS_SIGNALING` is labelled exploratory,
  from `gold_release`.
- It does not compare the two sets' score sizes.

**Soft criteria.** Reports the set's rank in the KRAS process
(`rank_in_process` 8) and the arms that supported it.

**Expected values.** None numeric. The label, ranks and alternative come from
the registry.

## S4 — The ATF4 score is inverted

> In Tahoe-100M, does Bortezomib activate the integrated stress response
> (ATF4) relative to vehicle?

**Expected route.** `list_releases()`;
`get_validated_signatures(process="ATF4")`;
`search_conditions(drug="Bortezomib")`; then
`get_pathway_scores(process="ATF4", drug=[...])`.

**Hard criteria.**

- The scored set is `IGARASHI_ATF4_TARGETS`, with `validated_v02` rows.
- The answer states the inversion from `score_direction_note`: a higher score
  means less ATF4 activity, so a falling score means more ATF4 activity.
- The conclusion is stated in process terms, and it matches the observed sign
  read through that inversion.
- The direction class is reported as `complex`, with the registry's
  `condition` text, not as a simple expected sign.

**Soft criteria.** Notes that the registry records the score falling with the
proteasome-inhibitor class on Tahoe-100M. Notes that the ISR is adaptive and
pro-survival, as the `condition` text says.

**Expected values.** The registry lists Bortezomib in the Tahoe-100M arm's
proteasome-inhibitor class, which lowers the score as a class. Bortezomib's own
per-line or median sign **needs an independent expected value** from the public
Tahoe-100M panel scores.

## S5 — A DepMap-only readout used for a drug effect

> In Tahoe-100M, does Pitavastatin suppress YAP signaling more than
> Pravastatin?

**Expected route.** `list_releases()`;
`get_validated_signatures(process="YAP")`; `search_conditions` for the labels
`Pitavastatin (Calcium)` and `Pravastatin (sodium)`; then
`get_pathway_scores(process="YAP", drug=[both])`.

**Hard criteria.**

- The scored set is `LIT_Zanconato2015_YAP_TEAD`, with `validated_v02` rows.
- The answer states that this readout was validated on DepMap genetics only:
  the Tahoe-100M arm was not testable and no drug class was shown to move it.
  The drug comparison therefore rests on genetic evidence alone.
- It gives the proliferation caveat: the readout correlates with
  proliferation, and the served scores carry no proliferation correction. It
  does not residualise the scores itself.
- It compares the two drugs on the same set only, plate for plate, and claims
  neither target engagement nor greater on-target potency.

**Soft criteria.** Notes that `CORDENONSI_YAP_CONSERVED_SIGNATURE`, used by
set-A prompt A5, passed validation but is not the readout.

**Expected values.** Which statin lowers the readout more **needs an
independent expected value** from the public Tahoe-100M panel scores.

## S6 — Control: a plain expression question is unaffected

> In Tahoe-100M, how does Trametinib at 5 µM change DUSP6 expression versus
> vehicle in A549?

**Expected route.** `list_releases()`; `resolve_genes(symbols=["DUSP6"])`;
`search_conditions(drug="Trametinib")`; then
`get_expression_slice(genes=["DUSP6"], conditions=["Trametinib"], include_matched_controls=true)`,
reading the A549 (`CVCL_0023`) rows, or the released-contrast route of E1.

**Hard criteria.**

- No call to `get_validated_signatures` or `get_pathway_scores`, and no
  validation language in the answer.
- The expression criteria of [E1](E1.md) for its route: a descriptive contrast
  from matched controls, the measurement named, no invented p-value.
- When both are available, run the case with the panel visible and with it
  hidden. The route and the answer do not change.

**Expected values.** None frozen; E1's expression route has none.

## S7 — An Emerald Bay pathway question

> In Emerald Bay, how does mTORC1 signalling respond in `<sample>` for
> `<cell line>`?

Replace the placeholders with a treated profile selected independently from
the public Emerald Bay release, as in the [Emerald pack](emerald-README.md).

**Expected route.** `list_releases()` with both Emerald and the panel visible;
`get_guide(dataset="emerald-bay", topic="differential-vision-scores")`;
`search_gene_sets(dataset="emerald-bay", query="MTORC1")`; then
`get_pathway_scores(dataset="emerald-bay", process="mTORC1", samples=[...], cell_lines=[...])`.

**Hard criteria.**

- `search_gene_sets` lists `HALLMARK_MTORC1_SIGNALING`, the mTORC1 readout,
  among the validated readouts first, and the answer uses it.
- The scores are reported as Emerald gold differential values. They are never
  called panel scores, and Tahoe-100M is never queried as a fallback.
- The answer states the scope: the readout was validated on Tahoe-100M and
  DepMap (plus the proprietary verdict), never on Emerald Bay data.
- The Emerald rules apply: no second control subtraction, time zero is not a
  drug effect, unavailable is not zero, and the CC BY 4.0 attribution is given.

**Expected values.** Two values **need independent confirmation** from the
public Emerald Bay release: that `HALLMARK_MTORC1_SIGNALING` is in its
differential VISION vocabulary, and the score for the chosen profile.

## S8 — An Emerald Bay process whose readout is custom

> In Emerald Bay, what does the KRAS pathway readout show for `<sample>` in
> `<cell line>`?

**Expected route.** `list_releases()` with both Emerald and the panel visible;
`get_pathway_scores(dataset="emerald-bay", process="KRAS", samples=[...], cell_lines=[...])`,
optionally after `get_validated_signatures(process="KRAS")`.

**Hard criteria.**

- The answer resolves KRAS to `PROGENY_MAPK_A` and reports that this readout
  has no Emerald Bay score: its rows have
  `value_status="gene_set_not_found"`.
- It substitutes no other set, such as `HALLMARK_KRAS_SIGNALING`, as the KRAS
  readout, and calls no substitute validated. If the user then asks for
  another set, that result is labelled exploratory and not validated on
  Emerald Bay.
- It does not fall back to Tahoe-100M scores, and does not report the missing
  value as zero.

**Expected values.** None numeric. That `PROGENY_` names are absent from the
Emerald vocabulary **needs independent confirmation** from the public Emerald
Bay release.
