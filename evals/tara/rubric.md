# Rubric

Per prompt: **PASS** requires every **hard** criterion; **soft** criteria are
reported but do not fail the run. A run also records the tool-call count and
whether the guide was read before the conclusion.

## Hard-fail classes

Any of these fails the run outright.

- **Wrong effect direction** — the claim runs opposite to the data.
- **Wrong or unstated control** — the comparison arm is missing or mismatched.
- **Re-subtracting a served contrast** — a vehicle or baseline value is
  subtracted from a value the release already publishes as a contrast.
- **Mechanism from annotation alone** — mechanism claimed from an annotation,
  an enrichment or a similarity, without a measurement.
- **NULL treated as "no effect" or zero** — an untested or unmeasured value read
  as evidence of absence.
- **Wrong label silently substituted** — a drug or cell-line label guessed or
  normalised (case, salt form) instead of confirmed.
- **A non-public dataset invented or sought** — a screen, panel or table outside
  the served release is used or looked for.
- **A dataset identity contract violated** — for the legacy Tahoe evaluations,
  report the public Cellosaurus ID or cell name, not an opaque line code. Emerald
  instead requires the returned canonical `cell_line_internal` key alongside
  cross-references and uncertainty; do not remove that public analysis key or
  turn an uncertain mapping into a confirmed identity.
- **A "significant count" as the headline** — a count of significant items
  presented as the result instead of an effect size with an interval.
- **A tool-less guess where a tool exists** — the answer is given without the
  retrieval the prompt requires.

## Additional Emerald hard failures

The [Emerald cases](emerald-cases.json) define their complete criteria and use
[the structured record](emerald-run-record.template.json). In addition to the
shared rules, any of these fails an Emerald case:

- Silent fallback to Tahoe-100M, a cross-dataset query or a reused foreign handle.
- Availability inferred from server 0.4.0 instead of account-visible capabilities.
- CPM normalized by the requested genes, the wrong logarithm, or a DESeq2 label
  applied to raw/CPM/log1p values.
- Combination labels split or simplified, controls collapsed, time zero treated
  as an endpoint control, or a join that multiplies sample/line rows.
- Clinical survival, significance or a recomputed phenotype substituted for the
  released in-vitro `growth_rate_released` value.
- Absolute VISION substituted for differential scores, or an unavailable score
  reported as zero.
- A truncated prefix presented as complete; simulated or synchronous execution
  presented as proof of a real pending/fetch/cancel path.
- Missing CC BY 4.0 source attribution, or runtime guidance redistributed under
  the plugin's separate documentation license.
- Candidate answers used as expected values, or criteria/tolerances loosened after
  inspecting a failing result.

An unavailable fixture, missing approval, blocked account or absent asynchronous
path is recorded as **BLOCKED**, not as a scientific or operational pass.

## Grading record

For each run, record:

| Field | Value |
|---|---|
| Prompt | E1 / E2 / … |
| Host | Claude Code / Codex CLI |
| Host version | |
| Model | |
| Tool calls | count, and whether each expected tool was called |
| `release` | |
| `guide_version` | |
| Guide read before conclusion | yes / no |
| Hard criteria | pass / fail, one line each |
| Soft criteria | noted, one line each |
| Verdict | PASS / FAIL |

## Rubric revisions

Criteria are never loosened to make a run pass. A change is made here, with its
reason, before any run is graded against it.

- **0.3.2, E1 — second route added, original kept.** The released differential
  expression tool was added after E1 was written. E1 keeps its expression-slice
  criteria unchanged; E1-DE adds route-specific criteria that keep the same hard
  requirements (direction, exact label, stated control, `n_cells` per contrast)
  and name the released log2 fold change as the measurement instead of
  `cpm_log1p`. A run is graded against the route it followed.
- **0.3.2, E2 — reference corrected.** An earlier reference line count (11) came
  from a first-row probe, not the tool; the tool lists 22. The criteria are
  unchanged; only the frozen value is corrected.
- **0.3.2, E5 — no expected biological pattern.** The prompt is new in the
  repository pack. It fixes no expected BRAF pattern in advance; the measured
  result is frozen instead.
- **0.3.2, E3–E5 and set A** are published as written; no criterion elsewhere
  changed.
