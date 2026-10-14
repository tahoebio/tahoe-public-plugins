# Compatibility

> Only tested combinations are claimed. No untested cross-host claims.

## Tested hosts

**Codex CLI** and **Claude Code** — the only hosts claimed. The install paths in
`docs/install.md` and the steps in `docs/install-verification.md` target them.
The exact tested versions and date are recorded here once the clean-machine
checks pass; until then no version is claimed.

No other client is claimed.

## Requirements

- The Codex CLI or Claude Code.
- A Google account, and a browser, for sign-in.
- No Databricks account or credentials are required.

## Plugin and server versions

The plugin is frozen against a public server version. Both manifests declare the
floor in `extensions["com.tahoebio"]["minServerVersion"]`, and the skill's step 1
warns when the served `server_version` is below it instead of assuming the
published expected values hold.

| Plugin | Minimum server | Frozen against |
|---|---|---|
| 0.3.5 | 0.3.9 | `evals/tara/frozen-expected-0.3.x.md` |

The frozen expected values were first taken during the 0.3.9 → 0.3.10 upgrade
window (2026-10-12 and 2026-10-13) and **re-frozen on 2026-10-13 against server
0.3.21**. The served `release` did not change, so the values reproduce on either,
and 0.3.9 — the earliest server the values were taken on — remains the floor.
Values are re-frozen when `server_version`, `release` or `guide_version` changes;
the 0.3.21 re-freeze moved the `guide_version` pin (the guide's worked examples
changed at 0.3.19) and re-verified the E2, E3 and E5 values live.

## Not claimed

- Any host other than the Codex CLI and Claude Code.
- Cross-host support beyond those two.
- Offline data access.
- Any client that does not implement the documented sign-in flow.

Claims are added only with evidence: a tested host, a version, and a date.
