# Install

Tara is a plugin. Installing it connects your agent to the remote MCP server
`tahoe-public`; the service then delivers both the data and the guidance for
using it.

## Tested hosts

**Codex CLI** and **Claude Code** are the only hosts claimed (see
`docs/compatibility.md`).

## Install the plugin

This is the primary path: install the plugin from Tahoe's own marketplace.

### Codex CLI

```sh
codex plugin marketplace add tahoebio/tahoe-public-plugins
codex plugin add tara@tahoe-public
```

### Claude Code

```sh
claude plugin marketplace add tahoebio/tahoe-public-plugins
claude plugin install tara@tahoe-public
```

### One prompt instead

Ask your agent to install the plugin from the marketplace above. The prompt
installs the **plugin**, not just a bare server entry.

### Finish the install

- Complete the **GitHub sign-in** the client opens. Approve the consent screen;
  the credential is stored by the client and no token is copied by hand.
- **Reload the plugin or start a new session** so the tools appear. A plugin
  installed without an interactive terminal connects in the next session.

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

`codex mcp add` starts the sign-in flow itself. This route skips the plugin
metadata, so it is documented as a fallback rather than the primary install.

## What the plugin ships

Connection manifests and one skill:

- `plugins/tara/plugin.json` and `plugins/tara/mcp.json` — the portable
  Codex pair: one `streamable-http` server named `tahoe-public` at
  `https://tara.tahoebio.io/mcp`.
- `plugins/tara/.claude-plugin/plugin.json` — the native Claude manifest, with
  the same server inline as type `http`.
- `plugins/tara/skills/tara/SKILL.md` — the `tara` skill: when to use it, the
  call order, the routing table and the analysis contract in brief, with four
  references under `skills/tara/references/`. It teaches the agent to route a
  Tahoe-100M question to the right tool; the data itself is served at runtime.

None of the manifests embeds credentials; authentication is handled by the
sign-in flow above. Both hosts discover the `skills/` directory by convention, so
no manifest field declares it.
