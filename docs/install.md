# Install

Follow the [served install guide](https://tara.tahoebio.io/install.md) for the
current installation commands, client-owned sign-in and per-client next steps.
That guide is the canonical procedure; this page records plugin-specific notes.
Sign in with any verified email address or a Google account.

## Older connections and installation ownership

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

For a direct server entry, use the served guide's advanced path. Keep one
`tahoe-public` connection and use its owning installation path for recovery.

## Verify

Follow the per-client handoff in the served guide, then call `list_releases`
through the same client connection. A successful call verifies readiness;
opening a browser or seeing a tool listing alone does not.
See [install verification](install-verification.md) for the clean-machine checklist.

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
client-owned sign-in flow in the served guide. Both hosts discover the `skills/`
directory by convention, so no manifest field declares it.
