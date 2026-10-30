# Tara eval pack

Correctness-graded prompts for the `tara` skill. This pack is public-safe and is
not part of the release archive. It uses host-neutral Markdown prompts and
structured evidence records; an offline contract test is not a live agent run.

## Dataset-specific packs

- **Tahoe-100M:** existing `E1.md` through `E5.md`, `set-A.md`,
  `frozen-expected-0.3.x.md`, `rubric.md` and `run-log.template.md`. Existing
  prompts and historical numeric records are retained unchanged.
- **Emerald Bay:** [full eval pack](emerald-README.md), including 23 cases,
  independent source expectations and strict Codex/Claude Code evidence records.
  The feature contract starts at server 0.4.0, subject to account-visible
  capabilities. These new cases are prepared; real remote sessions have not run.
- **Validated signatures:** [S1–S8](signatures.md). See the section below.

## Validated signatures (S1–S8)

[signatures.md](signatures.md) checks that the skill prefers the validated
readout for a pathway or program question, reads each row's `score_source` and
`validation_status`, and keeps the panel's caveats:

| Case | Checks |
|---|---|
| S1 | A MAPK inhibitor is scored on `PROGENY_MAPK_A`. |
| S2 | Apoptosis has no validated readout, and nothing is substituted. |
| S3 | `HALLMARK_KRAS_SIGNALING` was tested for KRAS but is not the readout. |
| S4 | The ATF4 readout's inverted score direction. |
| S5 | A DepMap-only readout used for a drug effect carries the caveat. |
| S6 | Control: a plain expression question is unaffected. |
| S7 | Emerald Bay: the validated name ranks first, gold scores, scope caveat. |
| S8 | Emerald Bay: a custom readout returns not-found rows, with no substitute. |

The cases need server 0.5.0 or later and the panel in the account's discovery
(`validated_signatures` on the Tahoe-100M entry); otherwise every case except
S6 is BLOCKED. Criteria come only from the public registry served by
`get_validated_signatures` and from public Tahoe-100M and Emerald Bay data. No
number is frozen. S1, S4, S5, S7 and S8 name the values that need independent
expectations, and their dependent criteria stay BLOCKED until those exist.
These cases are prepared only; no real remote session has run them.

The existing Tahoe prompts are unchanged. The sets that E4 and set-A prompts
A2, A3 and A5 name passed validation but are not readouts, so with the panel
visible they still read the released VISION store (`gold_release`). Their
frozen values keep their recorded scope, but an answer must now call them
exploratory. The Emerald pack keeps its 0.4.0 tool contract of 17 tools; S7
and S8 cover the panel on Emerald Bay.

## How to run

1. Install the pinned candidate using [the installation instructions](../../docs/install.md).
   The user completes sign-in. Start one fresh session per prompt per host.
2. Record host/version, model, plugin revision, public server version, dataset,
   release and guide hash. Use only capabilities currently advertised to that
   account. Never transfer a dataset's numeric expectations to another dataset.
3. Run the instantiated prompt and capture redacted transcript/tool evidence.
4. Grade every hard criterion. Missing, blocked or unrun cases cannot pass.
5. Record Tahoe runs in `run-log.template.md`; use the Emerald-specific structured
   record and checker for Emerald. No real test is authorized by an offline pass.

## Expected values

The existing Tahoe freeze records historical reference-service observations;
its exact recorded release/version scope remains in that file. It is neither
an Emerald expectation set nor evidence that this candidate has passed.

New Emerald expectations are derived from independent pinned released source
before inspecting candidate answers, following [emerald-oracle.md](emerald-oracle.md).
Candidate MCP output must never become its own expected answer. No Emerald
numeric values or successful live run have been invented or frozen here.
