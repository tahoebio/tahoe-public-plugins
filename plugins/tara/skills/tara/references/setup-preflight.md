# Resume setup in the active client

Use this preflight when public Tara setup is requested or its tools are missing.
The agent observes the host and executes supported client actions; the packaged
`plugins/tara/scripts/preflight.py` helper chooses one next action from those
observations. It is a local planner, not an OAuth client or a standalone probe.
It cannot inspect a different chat's tool connection. Python 3.10+ is required.

The served install guide linked from the repository README owns the
install/login commands.
Preserve host-required approvals. Never read credential files, inspect or print
credentials, copy tokens, retain authorization/callback URLs, or automate the
sign-in page. Let the client open its own browser and the user complete consent.

## Gather fresh evidence

1. Identify the active host and version from its own interface or `codex --version`
   / `claude --version`. Check its command help before claiming interface support.
   A known name alone does not establish a supported version. Unknown or
   unsupported interfaces remain blocked; do not invent flags or infer support
   from an arbitrary version floor.
2. Inspect plugin/server registration using the client's supported listing.
   For Codex, use `codex plugin list` and `codex mcp list`; for Claude Code use
   `/plugin` and `/mcp`. Read the public connection's status only; do not dump
   full configuration, environment variables or credential-bearing JSON.
   Preserve an existing plugin or direct connection. Add only a missing
   marketplace/plugin; never create a duplicate direct entry beside the plugin.
3. Read authentication status from the client. The word **OAuth** can identify a
   supported auth method without proving a current login. Ambiguous status is
   `unknown`, not `missing`. If login is pending, preserve its terminal and wait
   for that same attempt. Poll its result at most once per turn; after five
   minutes report that it is still waiting, rather than automatically retrying.
   A wait deadline does not mean the client's attempt ended. Use `timed_out`,
   `failed` or `cancelled` only after the client confirms a terminal result.
4. If login is missing, the returned Codex action starts
   `codex mcp login tahoe-public` in a persistent terminal. Request a necessary
   sandbox escalation if blocked; if denied, report the blocked stage. Claude
   Code returns the user action `/mcp` → `tahoe-public` → Authenticate. Do not
   start a parallel browser flow. A browser opening or consent click is not a
   successful login result.
5. After authentication, start a new Codex session or restart Claude Code if
   tools need reloading. Carry forward only this checklist, the journal location,
   and attempt numbers. In the new session, inspect the available tools again.
   If they remain missing after one reload, report `tools_missing` and diagnose
   the connection; do not reinstall or repeat OAuth just to refresh tools.
6. When instructed, make one bounded `list_releases()` call through **that
   session's `tahoe-public` MCP connection**, using the client's normal timeout
   (at most 60 seconds if configurable). A public HTTP health page, another
   client, cached response, or a test fixture cannot supply this witness.
   Require `ok: true`, `status: ok`, a usable `server_version` and a nonempty
   `releases` list. Normalize only the fields below. Record actual release IDs
   and version in the local verification report, with no credentials or handles.
   Report service failures honestly and respect retry hints; do not infer an
   auth failure from every network/service error. One explicit witness retry is
   allowed per session, only after the previous attempt ended.

## Run the helper

Resolve `scripts/preflight.py` under the installed plugin root (three parents
above this reference file's directory). Do not assume a machine-specific cache
path. Use one private, local journal file per host installation and public
connection, shared across all setup attempts and sessions. Create its parent
folder using normal host approval rules. Do not choose a new journal to bypass
an outstanding action. All cooperating agents must use this same journal.

Pass only sanitized observations on stdin; never pipe a raw client response or
credential store into the helper. This example represents an authenticated
connection awaiting its first witness; replace every field with observed state:

```json
{
  "host": "codex",
  "host_version": "0.162.1",
  "interface": "supported",
  "installation": "plugin",
  "authentication": "authenticated",
  "login": "idle",
  "install_attempt": 0,
  "login_attempt": 0,
  "session": "current",
  "session_tag": "session_a",
  "tools": "available",
  "witness_status": "not_run"
}
```

```sh
python3 <plugin-root>/scripts/preflight.py --journal <private-local-journal> < observations.json
```

`session_tag` is a new nonsecret label for each actual client session, not an
OAuth handle or a real session credential. Reuse it within the same session.
`install_attempt` and `login_attempt` refer to the action numbers returned by
this journal; initially use zero. Once the journal returns an attempt number,
echo it with every later observation about that action until the journal
settles or replaces it. A claimed installation settles when the client shows
the plugin or a direct connection and the observation names that same attempt;
the claim then clears, so a later real removal can start a fresh attempt. A
stale attempt number never settles or releases a newer claim. An ended failure
must name the actual attempt that ended. This prevents replaying an old failure
as permission to start a second flow. Do not label an attempt ended merely
because the agent lost its terminal handle. Preserve the journal and report
`login_result_unknown`.

Observation values:

| Field | Values |
|---|---|
| `host` | `codex`, `claude_code`, `other` |
| `interface` | `supported`, `unsupported`, `unknown` |
| `installation` | `absent`, `plugin`, `direct`, `failed`, `never_started`, `unknown` |
| `authentication` | `authenticated`, `missing`, `unknown` |
| `login` | `idle`, `pending`, `cancelled`, `failed`, `timed_out`, `never_started` |
| `session` | `current`, `reload_required`, `unknown` |
| `tools` | `available`, `missing`, `unknown` |
| `witness_status` | `not_run`, `succeeded`, `failed`, `unavailable`, `unauthorized`, `timed_out` |

For `witness_status: succeeded`, add this normalized `witness` object, populated
from the actual current-client result (the version below is illustrative):

```json
{
  "connection": "tahoe-public",
  "tool": "list_releases",
  "transport": "client_mcp",
  "session_tag": "session_a",
  "ok": true,
  "status": "ok",
  "server_version": "0.3.29",
  "release_count": 1
}
```

The helper trusts the agent's observations; it does not independently certify
that a submitted JSON object came from the client. Never manufacture evidence.
A success response has `stage: ready`, `ready: true`, exit code 0. Every other
stage has `ready: false`, an exact next action, and exit code 2. Do not interpret
exit code 2 as a request to repeat setup. Execute a returned action once, then
re-observe the client. Successful readiness is never cached in the journal.

The journal claims installation, login and witness work **before** returning an
action. Repeated or concurrent invocations will not issue the same pending
work. It cannot stop a human or another tool from independently starting OAuth;
check the client's own pending state as well. If a process dies between claiming
and executing, resolve that claim against the host before continuing.

A claim whose action was confirmed never started is reported as
`never_started` for that field, naming the claimed attempt and passing
`--retry`; the journal then issues one fresh attempt with a new number.
Confirmation must be positive evidence: the agent's own record shows the
returned action was never executed, and the client shows no pending or running
attempt. An idle or absent status, a lost terminal handle, a client restart or
elapsed time never proves an attempt never started. If the action may have run,
the claim stays unresolved until the client positively confirms it ended; the
`cancelled`, `failed` or `timed_out` observations then apply. The same rule
covers a pending login this journal adopted from the client: its disappearance
is not an ending. The lock never expires automatically. Remove an interrupted
lock/temporary file only once its process is confirmed ended; preserve the
journal and its action claims.

Use `--retry` only after the user explicitly asks to resume a cancelled/failed
attempt the client confirms ended, or an attempt positively confirmed never
started. It never overrides pending login or an unresolved action claim. A
stale failure's attempt number cannot authorize another login. Unknown state
remains unknown; do not delete the journal to make it look fresh. No telemetry
is collected or sent.

## Verification record

For a clean-session acceptance check, record date, OS, exact host/version,
plugin revision, installation path (plugin/direct), each observed stage,
required approvals, reload/new-session result, discovered tool names and the
actual read-only witness's server version and release IDs. Record unfinished
stages and their next action. Exclude secrets, authorization URLs and handles.

Run the existing repository clean-machine checklist too. The expression-slice
example is maintained in plugins PR #16; this preflight uses `list_releases`
and does not replace or duplicate that scientific verification step. Hermetic
helper tests do not certify fresh-user OAuth or an untested host/version.
