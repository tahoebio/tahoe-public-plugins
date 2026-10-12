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
- **An internal cell code echoed** — a result reports a code that is not the
  public Cellosaurus id or the cell name.
- **A "significant count" as the headline** — a count of significant items
  presented as the result instead of an effect size with an interval.
- **A tool-less guess where a tool exists** — the answer is given without the
  retrieval the prompt requires.

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
