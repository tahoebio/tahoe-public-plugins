# Independent Emerald expectations

Expected values must come from the pinned released source or an independently
verified released-data oracle. **Do not freeze candidate MCP answers, plugin
responses, screenshots or cached agent conclusions as expected values.** No
Emerald numeric freeze is committed here. The Tahoe historical freeze is not an
Emerald oracle.

## Source and reproducibility record

Record the public [EmeraldBay source](https://huggingface.co/datasets/tahoebio/EmeraldBay),
its immutable 40-character commit, source-data license, extraction/derivation script revision,
and artifact checksums. A source oracle must expose only approved scientific
fields and public identifiers. Keep credentials, operational metadata and
runtime guide text out of the expectation artifact.

Select fixtures deterministically before examining candidate results. Save the
selection rule, resulting exact keys, complete expected records, and independent
reviewer's approval time. If a required scientific class cannot be reconstructed
from the pinned source, mark the case blocked; do not guess values or substitute
a candidate answer. Use the source files and the independently recorded release
mapping to align gene tokens, sample keys and QC populations.

The oracle implementation must not import the candidate plugin, server query
builders, their result-shaping helpers or candidate outputs. Standard numeric
and table libraries are suitable. Preserve original released doubles and integer
counts; record derivations separately from released measurements.

## Required fixture classes

| Fixture | Independent selection and expected evidence |
|---|---|
| Measured profile | Exact sample/line key, complete sparse counts, full profile total, full-QC cell count and population |
| Positive and second gene | Unique Ensembl identities with measured-axis membership and positive counts; choose a subset whose sum differs from the profile total |
| Measured zero | A measured-axis gene whose count is zero in a measured profile, including sparse omission where applicable |
| Vocabulary-only gene | Valid released vocabulary entry absent from the measured gene axis; expected value is null |
| Unknown gene | Deterministic sentinel proven absent from the pinned symbol and Ensembl vocabulary |
| Ambiguous symbol | All exact candidates, token and Ensembl identities, and candidate count; no selected expression value |
| Absent profile | A sample/line lattice entry without measured expression; expected expression values and denominator are null |
| Combination and controls | Full condition tuple, every matching sample key, four separate endpoint controls and time-zero identity |
| Uncertain line | Canonical line key, cross-references and the released uncertainty label |
| Growth | Exact released growth value plus minimal/full/all-cell counts and separate phenotype/expression population fields |
| Differential VISION | Exact profile/signature keys and positive, negative, and near-zero or zero released values; record thresholds used to select near-zero values before the run |
| Scored time-zero VISION | A scored DMSO_T0 sample/line and signature with its exact released differential value, is_time_zero=true and is_control_reference=false; record the DMSO_TF endpoint-control reference definition |
| VISION availability | Endpoint-control references, an absent group and a below-cell-floor profile with expected null values and availability classes; time-zero identity alone is not an exclusion |
| Single-cell raw | Exact barcode and a bounded aligned token/count slice that actually contains an explicit stored zero; stored-entry and nonzero counts are checked independently |
| Mixed datasets | A separate pinned Tahoe source oracle; neither dataset's frozen values or metadata stand in for the other |

Do not invent a biological direction to fill a fixture. If the required sign,
zero, ambiguity or uncertainty is absent from the source, record the missing
fixture and block that case. Expected treatment effects are data, not assumptions.

## Expression calculation

For a measured sample/line profile, align its gene tokens and raw integer counts.
Check that tokens are unique, count arrays align, and the sum across the complete
profile equals the recorded total. Resolve each requested gene against the
independent vocabulary and measured axis.

- `raw_counts` is the integer profile count.
- `cpm = 1000000 * raw_counts / full_profile_total`.
- `cpm_log1p = ln(1 + cpm)` using the natural logarithm.

A sparse omission is zero only for a measured-axis gene in a measured profile.
Unknown, ambiguous, vocabulary-only or unavailable measurements stay null.
An invalid or missing denominator never justifies an invented zero. A measured
profile retains its whole total even when the requested gene is unmeasured or
ambiguous; an absent profile has no denominator.

Calculate the same positive gene alone and with additional genes. The expected
value and denominator must not change. Keep all four endpoint controls as separate
sample-level records for the same line; do not treat cells or genes as independent
control replicates or substitute time zero for an endpoint control.

## Released growth and pathways

Compare `growth_rate_released` exactly as released. It is a five-day in-vitro
response; do not rebuild it from a different population or reinterpret it as
clinical survival. Preserve phenotype and expression QC fields in the expected
record even when the numeric response looks plausible without them.

Compare differential VISION `score` exactly as released. Keep sample/line and
signature identity, `score_kind=differential`, availability and scoring flags.
Select a scored `DMSO_T0` profile independently for EB12's `time_zero_sample`
and `time_zero_line` fixtures. Its released value is a baseline-versus-endpoint
contrast relative to the mean matched `DMSO_TF` endpoint controls, not a
drug-treatment effect. Preserve `is_time_zero=true` and
`is_control_reference=false`; do not classify that profile as reference-only.
Time-zero profiles below the cell floor or without expression remain unavailable.
Use source eligibility and released values, not time-zero identity alone, to
determine whether a score exists. Endpoint-control references remain unavailable.
Do not compute a new contrast or subtract controls a second time. A genuine
zero score differs from an unavailable score. No DESeq2, absolute VISION,
embedding or perturbation-marker values belong in this Emerald oracle.

## Fixed comparison rules

- Keys, candidate sets, integer counts, booleans, nulls and categorical metadata:
  exact equality, including row-set completeness and duplicate detection.
- Released floating-point values: preserve round-trip values and compare exactly;
  do not loosen tolerances to excuse a source or serialization mismatch.
- Calculated CPM/log1p: fixed relative tolerance `1e-9`, absolute tolerance `1e-12`.
- Truncated output: compare every returned row to the corresponding ordered
  source prefix. Validate a complete bounded response or bounded SQL aggregate
  separately before making panel-wide claims; do not reconstruct a large export
  through repeated partitions to bypass output limits.
- Final answers: check direction, population, sample unit, normalization, control,
  missingness and attribution against the evidence; numeric parity alone is not
  sufficient.

Store the oracle snapshot and derivation with SHA256 hashes, reviewer and review
time before candidate execution. Record a separate comparison artifact per
case/host. Changes to fixtures, tolerances or hard criteria require review before
rerunning; never alter them merely to turn a failed candidate into a pass.
