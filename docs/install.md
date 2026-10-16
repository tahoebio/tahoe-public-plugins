# Install

Tara is a plugin. Installing it connects your agent to the remote MCP server
`tahoe-public`; the service then delivers both the data and the guidance for
using it.

## Tested hosts

**Codex CLI** and **Claude Code** are the only hosts claimed (see
`docs/compatibility.md`).

## Install the plugin

This is the primary path: install the plugin from Tahoe's own marketplace. Run
the commands in a terminal, or ask your agent to start the client-owned flow.
On repeated setup, preserve an existing installation and authenticated connection.

### Codex CLI

Run these in a terminal, in order:

```sh
codex plugin marketplace add tahoebio/tahoe-public-plugins
codex plugin add tara@tahoe-public
codex mcp login tahoe-public      # client opens the browser; you complete sign-in
```

Then start a **new Codex session** so the tools load.

### Claude Code

```sh
claude plugin marketplace add tahoebio/tahoe-public-plugins
claude plugin install tara@tahoe-public
```

Then **restart Claude Code** and sign in with `/mcp` (or on first use).

### Ask your agent instead

Paste this prompt. The agent installs Tara and starts the client's sign-in;
you complete sign-in and consent in the browser opened by the client.

> Use curl to read https://tara.tahoebio.io/install.md and perform the setup to install Tara, start the client-owned sign-in if needed, and verify a read-only tool call.

The [served install guide](https://tara.tahoebio.io/install.md) is the canonical
client-login procedure. Host-required approvals still apply. Check existing
installation and authentication before adding anything or starting login.
Use the client's own flow; never start a second OAuth flow while one is pending.
Never inspect, print, copy or persist credentials or callback URLs. Do not drive
the sign-in page with browser automation. Client-owned browser launch is allowed.

### Finish the install

Sign in with **any verified email address, or a Google account**, in the browser
the client opens; the credential is stored by the client and no token is copied by hand. The tools load at session start, so
**restart the client** after installing — a plugin installed without an
interactive terminal connects in the next session.

> **Remove and re-add an older connection.** A `tahoe-public` connection added
> before 2026-10-14 uses the older sign-in flow. If that connection cannot
> authenticate, remove and re-add it using its owning installation path:
>
> - **Codex CLI** — for a direct entry, `codex mcp remove tahoe-public`, then
>   re-add it. For a plugin-owned entry, use `codex plugin remove tara@tahoe-public`
>   and `codex plugin add tara@tahoe-public`. Then sign in with
>   `codex mcp login tahoe-public`. Do not add a duplicate direct server entry.
> - **Claude Code** — `claude mcp remove tahoe-public` for a direct install, or
>   `/mcp` → disconnect and reconnect for a plugin install.

> **Codex "Run without daemon" dialog.** Codex may present a **Run without
> daemon** prompt the first time it uses this server. Continue without a daemon:
> `tahoe-public` is a remote HTTPS endpoint, so there is nothing to run locally.

## Resume setup

The plugin bundles a [resumable setup checklist](../plugins/tara/skills/tara/references/setup-preflight.md)
and a local `plugins/tara/scripts/preflight.py` planner. The agent supplies
sanitized observations from the active host, executes the returned next action
once, and resumes after sign-in or reload. The planner records no credentials
and makes no network calls; a working read-only client call is required for
`ready`. Unknown host or authentication state stays explicit.

## Verify

If tools do not appear, start a new Codex session or restart Claude Code, then
check the client tool listing again. Do not reinstall or repeat OAuth just because
the old session lacks tools. If authentication is unknown, report that state and
check the client; a browser launch alone is not evidence of success.

Ask the agent to list the available dataset releases through this same connection.
A successful call confirms
the connection and the signed-in account. The full step-by-step verification is
in `docs/install-verification.md`.

## Advanced: add the server directly

If you only want the MCP server and not the plugin:

```sh
codex mcp add tahoe-public --url https://tara.tahoebio.io/mcp
claude mcp add --transport http --scope user tahoe-public https://tara.tahoebio.io/mcp
```

Sign in as above — Codex with `codex mcp login tahoe-public`, Claude
Code on first use or via `/mcp` — then restart the client. This route skips the
plugin metadata, so it is documented as a fallback rather than the primary
install.

## What the plugin ships

Connection manifests and one skill:

- `plugins/tara/plugin.json` and `plugins/tara/mcp.json` — the portable
  Codex pair: one `streamable-http` server named `tahoe-public` at
  `https://tara.tahoebio.io/mcp`.
- `plugins/tara/.claude-plugin/plugin.json` — the native Claude manifest, with
  the same server inline as type `http`.
- `plugins/tara/skills/tara/SKILL.md` — the `tara` skill: when to use it, the
  call order, the routing table and response handling, with five
  references under `skills/tara/references/`. It teaches the agent to route a
  Tahoe-100M question to the right tool; data and detailed scientific guidance
  are served at runtime.

None of the manifests embeds credentials; authentication is handled by the
sign-in flow above. Both hosts discover the `skills/` directory by convention, so
no manifest field declares it.
