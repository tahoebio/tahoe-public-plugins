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

Any agent that can add a plugin (it installs and stops; **you** sign in
yourself): the agent cannot connect the server or sign you in — MCP sign-in is
done by the client, and the install writes outside the agent's sandbox, so the
agent must ask for permission. The prompt installs the **plugin** — not just a
bare server entry — and then stops. Paste it verbatim:

> Install the Tahoe plugin: add the marketplace tahoebio/tahoe-public-plugins, install the tara plugin, approving the permission prompt if asked. Then stop. Do not try to sign in or open a browser. Tell me to sign in myself and start a new session.

The agent installs and stops; **you** sign in and start a new session.

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

## Update Tara

> Install Tara from `tahoebio/tahoe-public-plugins` on the `main` channel (do
> not pin a version tag if you want updates). Claude Code: run
> `claude plugin marketplace add tahoebio/tahoe-public-plugins`, then
> `claude plugin install tara@tahoe-public`. Third-party marketplaces have
> auto-update **off by default**. In a Claude Code session run `/plugin` →
> **Marketplaces** → **tahoe-public** → **Enable auto-update**. Updates arrive
> after a session starts; use `/reload-plugins` when prompted or start a new
> session. To update now, run `claude plugin update tara@tahoe-public` in your
> shell, or select **Update marketplace** inside `/plugin`; the shell
> `claude plugin marketplace update` alone refreshes listings and does not
> update installed plugins. Codex CLI: run
> `codex plugin marketplace add tahoebio/tahoe-public-plugins --ref main`,
> `codex plugin add tara@tahoe-public`, then `codex mcp login tahoe-public` and
> start a new session. For later versions run
> `codex plugin marketplace upgrade tahoe-public` (or
> `codex plugin marketplace upgrade`) and start a new Codex session. Unattended
> Codex marketplace upgrades are not documented, so this explicit upgrade is the
> supported user path. Verify the installed Tara manifest shows `0.4.0`, then
> make a signed-in `list_releases` call and an Emerald call with
> `dataset="emerald-bay"`; Tahoe requests still work. Your account's release
> list is the access authority.

An organization **administrator**, not this repository, may centrally turn
Claude auto-update on using managed
`extraKnownMarketplaces["tahoe-public"]` with GitHub source,
`autoUpdate: true`, and `enabledPlugins["tara@tahoe-public"]: true`; that
requires a separate admin rollout and client repository read access.
[Claude install/update](https://code.claude.com/docs/en/discover-plugins),
[publisher guidance](https://code.claude.com/docs/en/plugins/host-marketplace),
[managed setting](https://code.claude.com/docs/en/plugins/org),
[marketplace source/ref](https://code.claude.com/docs/en/plugins/marketplace-reference),
[Codex package/marketplace CLI](https://developers.openai.com/plugins/build/plugins).

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
