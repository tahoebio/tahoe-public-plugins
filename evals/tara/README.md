# Tara eval pack

Correctness-graded prompts for the `tara` skill. This pack is **public-safe**
(no internal names) and is **not** part of the release archive.

## Format decision

Claude Code ships a `claude plugin eval` suite format: a directory of cases
under the plugin's eval directory, each with a `prompt.md` and a grader, run
against **mock** MCP servers by default. Running a real **remote** MCP server
(our `streamable-http` endpoint) inside that harness is not documented, and a
mock would not test the thing this pack exists to test — whether the agent
routes to the real tools and reads the real provenance.

So this pack is a **markdown pack plus a run log**, run by hand against the live
service. It is re-evaluated under `claude plugin eval` (or an equivalent) only
once a remote server is a documented, supported target.

## Files

- `E1.md` — the prompt, expected tools, and hard/soft criteria. Runs today.
- `E2.md` — needs the drug and cell-line tools; marked for a later family.
- `rubric.md` — the hard-fail classes and the grading rules.
- `run-log.template.md` — one record per run (host, model, transcript, tool log).

## How to run

1. Install the plugin from the local checkout (pre-publication) against the live
   host, or from the marketplace once published:
   `claude plugin install ./plugins/tara` (Claude Code) and the Codex
   equivalent.
2. One **fresh session per prompt per host**. Record the host, its version and
   the model.
3. Run the prompt as written. Capture the transcript and the tool-call log
   (tool, arguments, `release`, `manifest`, `guide_version`).
4. Grade with `rubric.md`: PASS requires every **hard** criterion; **soft**
   criteria are reported but do not fail the run.
5. Record the run in `run-log.template.md`.

## Freezing expected values

Numeric expected values (per-line deltas, score ranges) are frozen by the eval
author from **one reference run** against the live service at freeze time, and
recorded with the `release` and `guide_version` of that run. Direction and
structure criteria are fixed in the prompt file; only the numbers are frozen.
