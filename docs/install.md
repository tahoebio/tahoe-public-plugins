# Install

Tara is a plugin. Installing it connects your agent to the remote MCP server
`tahoe-public`; the service then delivers both the data and the guidance for
using it.

## Tested hosts

**Codex CLI** and **Claude Code** are the only hosts claimed (see
`docs/compatibility.md`).

## Install the plugin

This is the primary path: install the plugin from Tahoe's own marketplace. Run
the commands in a terminal — not through an agent, which cannot sign you in.

### Codex CLI

Run these in a terminal, in order:

```sh
codex plugin marketplace add tahoebio/tahoe-public-plugins
codex plugin add tara@tahoe-public
codex mcp login tahoe-public      # opens the browser: Allow Access → Google
```

Then start a **new Codex session** so the tools load.

### Claude Code

```sh
claude plugin marketplace add tahoebio/tahoe-public-plugins
claude plugin install tara@tahoe-public
```

Then **restart Claude Code** and sign in with `/mcp` (or on first use).

### Ask your agent instead

An agent can install the plugin, but it **cannot sign you in**: MCP sign-in is
done by the client, and the install writes outside the agent's sandbox, so the
agent must ask for permission. The prompt installs the **plugin** — not just a
bare server entry — and then stops. Paste it verbatim:

> Install the Tahoe plugin: add the marketplace tahoebio/tahoe-public-plugins, install the tara plugin, then connect to Tara. Approve the permission prompt if it asks, then stop — do not sign in or open a browser; I'll run `codex mcp login tahoe-public` myself and start a new session.

The agent installs and stops; **you** run the sign-in command and start a new
session.

### Finish the install

Sign-in is **Google**, in the browser the client opens; the credential is stored
by the client and no token is copied by hand. The tools load at session start, so
**restart the client** after installing — a plugin installed without an
interactive terminal connects in the next session.

> **Remove and re-add an older connection.** A `tahoe-public` connection added
> before 2026-10-14 predates the Google sign-in. Remove it and add it again so
> it signs in with Google:
>
> - **Codex CLI** — `codex mcp remove tahoe-public`, then re-add the server or
>   reinstall the plugin, and sign in with `codex mcp login tahoe-public`.
> - **Claude Code** — `claude mcp remove tahoe-public` for a direct install, or
>   `/mcp` → disconnect and reconnect for a plugin install.

> **Codex "Run without daemon" dialog.** Codex may present a **Run without
> daemon** prompt the first time it uses this server. Continue without a daemon:
> `tahoe-public` is a remote HTTPS endpoint, so there is nothing to run locally.

## Verify

Ask the agent to list the available dataset releases. A successful call confirms
the connection and the signed-in account. The full step-by-step verification is
in `docs/install-verification.md`.

## Advanced: add the server directly

If you only want the MCP server and not the plugin:

```sh
codex mcp add tahoe-public --url https://tara.tahoebio.io/mcp
claude mcp add --transport http --scope user tahoe-public https://tara.tahoebio.io/mcp
```

Sign in with Google as above — Codex with `codex mcp login tahoe-public`, Claude
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
  call order, the routing table and response handling, with four
  references under `skills/tara/references/`. It teaches the agent to route a
  Tahoe-100M question to the right tool; data and detailed scientific guidance
  are served at runtime.

None of the manifests embeds credentials; authentication is handled by the
sign-in flow above. Both hosts discover the `skills/` directory by convention, so
no manifest field declares it.
