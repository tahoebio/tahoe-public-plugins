# Install verification (clean machine)

> **Prepared for a human tester.** The sign-in step is interactive and is
> performed by a person, not by any script in this repository. Nothing here
> automates sign-in or stores a credential.

This is the clean-machine check for the two tested hosts (Codex CLI and Claude
Code). Its result is recorded in `docs/compatibility.md`.

## Prerequisites

- A machine that has never had the plugin or the `tahoe-public` server
  installed, with a current Codex CLI **and** Claude Code.
- Any verified email address or a Google account, and a browser available for the sign-in redirect.
- No Databricks account or credentials.

## Case A — plugin install from the marketplace (primary)

Run once per host.

1. Add the marketplace and install the plugin.

   Codex CLI:

   ```sh
   codex plugin marketplace add tahoebio/tahoe-public-plugins
   codex plugin add tara@tahoe-public
   ```

   Claude Code:

   ```sh
   claude plugin marketplace add tahoebio/tahoe-public-plugins
   claude plugin install tara@tahoe-public
   ```

2. Sign in with a verified email address or Google in the browser the client opens: Codex with
   `codex mcp login tahoe-public`, Claude Code on first use or via `/mcp`. If
   Codex shows a **Run without daemon** prompt, continue without a daemon — the
   endpoint is remote.
3. Restart the client (restart Claude Code, or start a new Codex session) so the
   tools load.
4. Call `list_releases` through the agent. Record the release identifiers.
5. Call `get_expression_slice` for a small, known request (for example two genes
   and two conditions) and record the returned provenance and request manifest.

## Case B — direct server add (advanced fallback)

```sh
codex mcp add tahoe-public --url https://tara.tahoebio.io/mcp
claude mcp add --transport http --scope user tahoe-public https://tara.tahoebio.io/mcp
```

Repeat steps 2–5. In Codex, sign in with `codex mcp login tahoe-public`.

## Evidence to capture

- Each exact command used, and each client's version.
- A screenshot or transcript of the consent screen, the marketplace listing, and
  the client's server/tool listing.
- The raw response envelopes for `list_releases` and `get_expression_slice`.
- Any prompt, warning or failure, verbatim — including a restart requirement.

## Pass criteria

- The plugin installs from the marketplace and reaches sign-in; the direct add
  also works.
- Sign-in succeeds with a verified email address or Google account and no manual token handling.
- The tools become callable after the restart step.
- Both calls return data, and the slice carries release, filters, measurement
  semantics, missing-value meaning and a repeatable request manifest.
- No Databricks credential was required.

## Recording the result

Add each tested host, its version and the date to `docs/compatibility.md`, and
note anything that differs from the steps above. A host is claimed as supported
only after this check passes end to end.

## Case C — end-to-end correctness eval

After Case A passes on a host, run the correctness pack in `evals/tara/`
(prompts E1–E5 and A1–A5) from the installed plugin, one fresh session per
prompt, and grade against `evals/tara/rubric.md` with the values in
`evals/tara/frozen-expected-0.3.x.md`. **Pass is the rubric's rule: every hard
criterion.** Also report separately whether any hard-fail class occurred; that
is information, not the pass rule.

- Pace the runs. The service allows a limited number of calls per user per hour;
  a back-to-back run of the whole pack returns `rate_limited`. Re-run a
  rate-limited prompt after the window rather than grading it, and mark it
  incomplete if it stays limited.
- Disable any other server or plugin named `tara` for the run, and check the
  transcript for reads of it.
- Record `server_version`, `release` and `guide_version` from each transcript.

First recorded run, Codex, two models, server 0.3.9–0.3.10 (2026-10-12/13):

- No hard-fail class occurred in any scored run, and every scored run loaded the
  skill.
- **Strict result: A1–A5 and E5 pass; E1, E2, E3 and E4 do not.** E1 omitted
  `n_cells` per contrast, E2 listed lines without Cellosaurus ids, E3 stopped at
  the survival score without the arrest/Augur cross-check, and E4 did not call a
  NULL `padj` "untested". One E4 run was also incomplete because the per-user
  call allowance was exhausted.
- Limitations: runs were first rate-limited and re-run paced; a second plugin
  named `tara` was present on the host and was read in some transcripts without
  being relied on.
- Claude Code and Cursor have not been run.
