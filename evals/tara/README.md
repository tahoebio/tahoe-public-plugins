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
