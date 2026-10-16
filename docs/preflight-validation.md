# Public setup preflight validation

## Local inspection — 2026-10-16

| Observation | Result |
|---|---|
| Host | macOS, Codex CLI 0.162.1 |
| Installed public plugin | Tara 0.3.4 skill is available |
| Supported listing interface | `codex mcp list` and plugin command help inspected |
| Public server listing | `tahoe-public`, enabled, Auth `Unknown` |
| Active session's public tools | Not exposed in this session |
| Helper result | `authentication_unknown`, `ready: false`, `inspect_authentication` |
| Installation/login actions issued | None; both attempt counters remain zero |
| Read-only witness | Not run; active client has no public tools |

This is an existing-installation inspection, **not clean-machine OAuth
acceptance**. No client credentials or configuration were changed. The planner
correctly preserves the installation and reports the missing evidence instead
of starting another login or claiming readiness. A fresh session with usable
client authentication and a successful `list_releases` call is still required.

## Hermetic coverage

The offline preflight tests cover fresh setup, an existing plugin or direct
connection, missing/unknown authentication, pending/cancelled/failed/timed-out
login, reload, missing tools, unsupported/unknown host interfaces, bounded
witness retries, stale/wrong-client witness rejection and successful readiness.
They also cover parallel action claims, repeated invocations, stale terminal
attempt numbers, interrupted locks, corrupt journals and rejection of unexpected
input without echoing it. Archive tests include the script and setup reference.

These tests use sanitized fixtures; they do not certify any host's live OAuth
behavior. Use the clean-machine checklist in `install-verification.md` and the
record format in the bundled setup reference to record end-to-end acceptance.
