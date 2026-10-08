# Install

Tara runs as a remote MCP server named `tahoe-public`. Install it with one
command, from the tested host below.

## Tested host: Codex CLI

The only host claimed as tested is the Codex CLI. No other client is claimed
(see `docs/compatibility.md`).

## Install

```sh
codex mcp add tahoe-public --url https://tara.tahoebio.io/mcp
```

This single command registers the server and starts the sign-in flow: Codex
opens a browser for GitHub sign-in. Approve the consent screen; the credential
is stored by Codex, and no token is copied by hand.

> **Codex "Run without daemon" dialog.** Codex may present a **Run without
> daemon** prompt the first time it uses this server. Continue without a daemon:
> `tahoe-public` is a remote HTTPS endpoint, so there is nothing to run locally.

## Verify

```sh
codex mcp list
```

`tahoe-public` should be listed. Then ask the agent to list the available
dataset releases; a successful call confirms the connection and the signed-in
account. The full step-by-step verification is in
`docs/install-verification.md`.

## Configuration shipped by the plugin

The plugin declares the same server in `plugins/tara/mcp.json`: a single
`streamable-http` server named `tahoe-public` pointing at
`https://tara.tahoebio.io/mcp`, with no embedded credentials. Authentication is
handled by the sign-in flow above.
