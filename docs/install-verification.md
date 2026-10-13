# Install verification (clean machine)

> **Prepared for a human tester.** The sign-in step is interactive and is
> performed by a person, not by any script in this repository. Nothing here
> automates sign-in or stores a credential.

This is the clean-machine check for the two tested hosts (Codex CLI and Claude
Code). Its result is recorded in `docs/compatibility.md`.

## Prerequisites

- A machine that has never had the plugin or the `tahoe-public` server
  installed, with a current Codex CLI **and** Claude Code.
- A GitHub account, and a browser available for the sign-in redirect.
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

2. Complete the sign-in: approve the GitHub consent screen in the browser the
   client opens. If Codex shows a **Run without daemon** prompt, continue
   without a daemon — the endpoint is remote.
3. Reload the plugin or start a new session, so the tools appear.
4. Call `list_releases` through the agent. Record the release identifiers.
5. Call `get_expression_slice` for a small, known request (for example two genes
   and two conditions) and record the returned provenance and request manifest.

## Case B — direct server add (advanced fallback)

```sh
codex mcp add tahoe-public --url https://tara.tahoebio.io/mcp
claude mcp add --transport http --scope user tahoe-public https://tara.tahoebio.io/mcp
```

Repeat steps 2–5. `codex mcp add` starts sign-in itself.

## Evidence to capture

- Each exact command used, and each client's version.
- A screenshot or transcript of the consent screen, the marketplace listing, and
  the client's server/tool listing.
- The raw response envelopes for `list_releases` and `get_expression_slice`.
- Any prompt, warning or failure, verbatim — including a reload/new-session
  requirement.

## Pass criteria

- The plugin installs from the marketplace and reaches sign-in; the direct add
  also works.
- Sign-in succeeds with a GitHub account and no manual token handling.
- The tools become callable after the reload/new-session step.
- Both calls return data, and the slice carries release, filters, measurement
  semantics, missing-value meaning and a repeatable request manifest.
- No Databricks credential was required.

## Recording the result

Add each tested host, its version and the date to `docs/compatibility.md`, and
note anything that differs from the steps above. A host is claimed as supported
only after this check passes end to end.

## Case C — end-to-end correctness eval

After Case A passes on a host, run the correctness pack in `evals/tara/`
(prompts E1–E5 and the five set-A questions) from the installed plugin, one
fresh session per prompt, two models per host, and grade against
`evals/tara/rubric.md` and the frozen values in
`evals/tara/frozen-expected-0.3.x.md`.

- Pace the runs. The service allows a limited number of calls per user per hour;
  a back-to-back run of the whole pack exhausts it and returns `rate_limited`.
  Space prompts out and re-run any that were rate-limited rather than grading
  them.
- Disable any other server or plugin named `tara` for the run, so the public
  plugin is the only one in play.
- Record `server_version`, `release` and `guide_version` from each transcript.
- Pass: no hard-fail class from the rubric occurs, and every scored run loaded
  the skill (read `SKILL.md` or called `get_guide`).

Codex was run on 2026-10-12/13 against server 0.3.9–0.3.10. Claude Code and
Cursor are not yet run.
