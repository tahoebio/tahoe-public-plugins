# Install verification (clean machine)

> **Prepared for a human tester.** The sign-in step is interactive and is
> performed by a person, not by any script in this repository. Nothing here
> automates sign-in or stores a credential.

This is the clean-machine check for the tested host (Codex CLI). Its result is
recorded in `docs/compatibility.md`.

## Prerequisites

- A machine that has never had the plugin or the `tahoe-public` server
  installed, with a current Codex CLI.
- A GitHub account, and a browser available for the sign-in redirect.
- No Databricks account or credentials.

## Steps

1. Install the server with the single documented command:

   ```sh
   codex mcp add tahoe-public --url https://tara.tahoebio.io/mcp
   ```

2. Complete the sign-in: approve the GitHub consent screen in the browser that
   Codex opens. If Codex shows a **Run without daemon** prompt, continue without
   a daemon — the endpoint is remote.
3. Confirm the server is registered:

   ```sh
   codex mcp list
   ```

4. Call `list_releases` through the agent. Record the release identifiers it
   returns.
5. Call `get_expression_slice` for a small, known request (for example two genes
   and two conditions) and record the returned provenance and request manifest.

## Evidence to capture

- The exact command used and the Codex CLI version.
- A screenshot or transcript of the consent screen and of `codex mcp list`.
- The raw response envelopes for `list_releases` and `get_expression_slice`.
- Any prompt, warning or failure, verbatim.

## Pass criteria

- The single command registers the server and triggers sign-in.
- Sign-in succeeds with a GitHub account and no manual token handling.
- Both calls return data, and the slice carries release, filters, measurement
  semantics, missing-value meaning and a repeatable request manifest.
- No Databricks credential was required.

## Recording the result

Add the tested host, the Codex CLI version and the date to
`docs/compatibility.md`, and note anything that differs from the steps above.
A host is claimed as supported only after this check passes end to end.
