# Emerald Bay plugin evaluations

**Status: prepared, not run against the real MCP.** This pack defines the complete
first-release plugin checks. Its files are public-safe and stay outside the
plugin release archive. No result here claims that a fresh Codex or Claude Code
session has passed.

The Emerald feature contract starts at server **0.4.0**. Availability still comes
from the account-visible `list_releases` response. A version string does not grant
access or establish that a tool, release or measurement is supported. Existing
Tahoe-100M evaluations and their historical frozen values remain separate.

## Files and coverage

- [emerald-cases.json](emerald-cases.json): 23 prompts with fixture inputs,
  expected tool routes and individually identified hard criteria.
- [emerald-oracle.md](emerald-oracle.md): how to prepare independent expected
  values before examining candidate results.
- [emerald-run-record.template.json](emerald-run-record.template.json): empty
  acceptance record; no sessions or numeric results have been invented.
- [emerald-record.schema.json](emerald-record.schema.json): record structure.
- [check_emerald.py](check_emerald.py): offline structural and completeness checks.

| Cases | What they verify |
|---|---|
| EB01 | Account-visible capabilities, exact dataset, guide, release and rights |
| EB02–EB05 | Raw pseudobulk, CPM, natural-log log1p(CPM), full-profile denominator and subset invariance |
| EB06–EB07 | Measured zero, absent profile, vocabulary-only/unknown gene and ambiguous identity |
| EB08–EB09 | Complete combinations, separate matched controls, time zero, line uncertainty and metadata limits |
| EB10 | Released five-day in-vitro growth response and distinct QC populations |
| EB11–EB12 | Differential VISION values, signs, controls and unavailable states |
| EB13 | Bounded single-cell raw reads, explicit zeros and aligned sparse arrays |
| EB14 | Explicit refusal of unsupported Emerald measurements; no dataset substitution |
| EB15, EB17 | Offline compatibility fixtures for an older server and missing/inconsistent capabilities |
| EB16 | Real authorized Tara account without Emerald visibility |
| EB18 | Intentional two-dataset analysis with separate guides, queries and provenance |
| EB19–EB21 | Actual truncation, pending/fetch and owned terminal cancellation |
| EB22 | Attribution, transformations, populations and limits in the final answer |
| EB23 | Separately approved synthetic feedback receipt |

Every case is required on **Codex and Claude Code**: 46 case/host records. EB15 and
EB17 are explicitly offline compatibility cases; their four records do not count
as real MCP evidence. The other 42 records require actual remote sessions. All
17 service tools are accounted for: supported routes, shared operations, and
three shared tools whose Emerald capability is explicitly unsupported. An agent
need not invoke a known unsupported tool merely to repeat its documented refusal.

## Prepare a session

1. Get separate approval for the real service test window and test identities.
   Installing this pack or running offline tests does not grant that approval.
   EB23 also needs explicit approval to submit synthetic feedback.
2. Prepare and independently review the oracle described below. Record its source
   immutable 40-character source commit, derivation and snapshot hashes before
   seeing candidate answers.
3. Pin the candidate plugin commit. Use the same candidate on both hosts and
   record each host version and model. Run one fresh session per prompt; never
   reuse prior chat answers as context or as expected data.
4. Replace prompt fixture placeholders with the independently selected public
   identifiers. Save the exact instantiated prompt. Do not substitute a profile
   or gene because the candidate returns a more convenient answer.
5. Use the configured public MCP endpoint. Do not alter it, change identities,
   relax limits or change dataset access to make a failing case pass.

Read the relevant case's hard criteria before execution. Keep criteria separate
from the prompt shown to the agent so the transcript tests the plugin's behavior,
not a supplied solution. For EB15/EB17, use recorded metadata-only fixture
responses with no real warehouse and label the result `offline-contract`.
For EB16, use an ordinary authorized account outside Emerald access; do not
assume the reason that Emerald is hidden.

## Grade results

A reviewer compares every returned scientific row against independently frozen
expectations, including keys, flags, missingness and denominator metadata. Use
exact comparisons for integers, nulls, categorical values and released doubles;
only calculated CPM/log1p use the predeclared tolerance. Review the final prose
as well as tool arguments and results. A correct number with a wrong population,
normalization, control, or unsupported causal claim fails.

Record `pass`, `fail`, `blocked` or `not_run` per case and per hard criterion.
Missing fixtures, unavailable access, failed source reconstruction, absent
approval, rate limits or a missing pending/cancel path cannot become a pass.
A synchronous result does not prove pending handling, and a completed query does
not prove cancellation. Do not generate expensive work merely to force those
paths. A case can remain blocked until an approved bounded workload is available.

Retain redacted transcripts, tool traces and row-by-row comparisons outside the
repository. Use relative artifact references and SHA256 hashes in the record.
Do not commit credentials, result/cancel handles, account identifiers, deployment
information or runtime guide text. A guide hash and the relevant topic names are
sufficient to record what the agent read.

The record includes each run's public endpoint, server version, plugin commit,
release, guide hash, host version, model, fresh-session label and reviewer. Record
all criteria, not just the passing ones. Preserve the exact public sample/line
and gene/signature keys in the scientific comparison evidence. These keys are
part of the analysis contract, not a claim of externally confirmed identity.
Use ISO timestamps with an explicit timezone for oracle review and session start.
The review must precede every candidate session. Only set record status to
`reviewed` after completing the evidence review. Emerald-available sessions must
record a numeric server version of at least `0.4.0`; the older-server fixture
retains its actual older version.

## Offline commands

Run these from the repository root after `uv sync`; they use the existing
development dependencies and none makes an MCP call:

```bash
uv run python evals/tara/check_emerald.py
uv run python evals/tara/check_emerald.py --record evals/tara/emerald-run-record.template.json
```

The first command verifies pack structure and reports
`live_verification: not_performed`. The empty template deliberately exits `1`
with readiness false. An unreadable or invalid input exits `2`.

For a completed record, `pack_sha256` is the SHA256 of the parsed pack serialized
with Python `json.dumps(pack, sort_keys=True, separators=(",", ":"))`, encoded as
UTF-8. Artifact hashes are SHA256 of their exact bytes. Never copy a saved `ready`
flag: the checker validates the record schema and recomputes case/host coverage,
criteria, evidence kinds and required metadata. Missing, duplicate, blocked,
unrun or failed records prevent readiness.

The checker verifies **evidence completeness**, not whether a transcript or
reviewer's assertions are true. A human must inspect the linked evidence and
independent oracle. A complete record does not authorize deployment, dataset
activation, plugin release or feedback submission. Real server verification and
this fresh-session plugin pack are separate evidence requirements.
