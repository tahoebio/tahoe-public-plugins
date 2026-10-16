"""Plan one public Tara setup step from sanitized observations of the active client.

This helper neither reads client configuration/credentials nor runs host commands.
The agent gathers evidence using the supported client interface and executes the
returned action. A local journal claims each action BEFORE it is returned, so a
second invocation cannot start duplicate installation, login or witness work.
A claim settles only when that same attempt is observed complete; an attempt
confirmed never started resumes only through an explicit retry naming it.
Only sanitized enums and counters are persisted; readiness is never persisted.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path

ENUMS = {
    "host": {"codex", "claude_code", "other"},
    "interface": {"supported", "unsupported", "unknown"},
    "installation": {"absent", "plugin", "direct", "failed", "never_started", "unknown"},
    "authentication": {"authenticated", "missing", "unknown"},
    "login": {"idle", "pending", "cancelled", "failed", "timed_out", "never_started"},
    "session": {"current", "reload_required", "unknown"},
    "tools": {"available", "missing", "unknown"},
    "witness_status": {
        "not_run",
        "succeeded",
        "failed",
        "unavailable",
        "unauthorized",
        "timed_out",
    },
}
WITNESS_FIELDS = {
    "connection",
    "tool",
    "transport",
    "session_tag",
    "ok",
    "status",
    "server_version",
    "release_count",
}
VERSION = re.compile(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?")
TAG = re.compile(r"[A-Za-z0-9_-]{1,32}")
MAX_BYTES = 4096


class InvalidEvidence(ValueError):
    pass


def validate(evidence):
    # No arbitrary error strings, URLs, environment variables or tool envelopes.
    required = set(ENUMS) | {
        "host_version",
        "session_tag",
        "install_attempt",
        "login_attempt",
    }
    if (
        not isinstance(evidence, dict)
        or not required <= evidence.keys()
        or evidence.keys() - required - {"witness"}
    ):
        raise InvalidEvidence("Use only the documented sanitized observation fields.")
    for key, choices in ENUMS.items():
        if not isinstance(evidence[key], str) or evidence[key] not in choices:
            raise InvalidEvidence("An observation enum is invalid.")
    for key, pattern in (("host_version", VERSION), ("session_tag", TAG)):
        if not isinstance(evidence[key], str) or not pattern.fullmatch(evidence[key]):
            raise InvalidEvidence(
                "Use a numeric host version and a short, nonsecret session label."
            )
    for key in ("install_attempt", "login_attempt"):
        if type(evidence[key]) is not int or not 0 <= evidence[key] <= 1_000_000:
            raise InvalidEvidence(
                "Use the action attempt number returned by this journal."
            )
    witness = evidence.get("witness")
    if witness is not None:
        if not isinstance(witness, dict) or set(witness) != WITNESS_FIELDS:
            raise InvalidEvidence("Use only the documented sanitized witness fields.")
        # Validating evidence does not mean the witness succeeded.
        if (
            witness["connection"] != "tahoe-public"
            or witness["tool"] != "list_releases"
            or witness["transport"] != "client_mcp"
            or not isinstance(witness["session_tag"], str)
            or not TAG.fullmatch(witness["session_tag"])
            or type(witness["ok"]) is not bool
            or witness["status"] not in ("ok", "error")
            or not isinstance(witness["server_version"], str)
            or not VERSION.fullmatch(witness["server_version"])
            or type(witness["release_count"]) is not int
            or not 0 <= witness["release_count"] <= 100
        ):
            raise InvalidEvidence(
                "The witness must describe the public client's list_releases call."
            )
    return evidence


def fresh_journal(host):
    return {
        "schema": 1,
        "host": host,
        "install_claimed": False,
        "login_claimed": False,
        "install_attempt": 0,
        "login_attempt": 0,
        "witness_session": "",
        "witness_attempts": 0,
    }


def valid_journal(journal, host):
    expected = fresh_journal(host)
    return (
        isinstance(journal, dict)
        and set(journal) == set(expected)
        and journal["schema"] == 1
        and journal["host"] == host
        and type(journal["install_claimed"]) is bool
        and type(journal["login_claimed"]) is bool
        and all(
            type(journal[k]) is int and 0 <= journal[k] <= 1_000_000
            for k in ("install_attempt", "login_attempt")
        )
        and isinstance(journal["witness_session"], str)
        and (
            journal["witness_session"] == ""
            or TAG.fullmatch(journal["witness_session"])
        )
        and type(journal["witness_attempts"]) is int
        and 0 <= journal["witness_attempts"] <= 2
    )


def step(evidence, journal, retry=False):
    """Return a fixed, secret-free action; mutate only the journal's claims."""
    e = validate(evidence)
    if not valid_journal(journal, e["host"]):
        raise InvalidEvidence(
            "Journal is invalid or belongs to another host; preserve it and inspect setup state."
        )

    def result(stage, action, next_action):
        return {
            "stage": stage,
            "ready": stage == "ready",
            "action": action,
            "next_action": next_action,
            "install_attempt": journal["install_attempt"],
            "login_attempt": journal["login_attempt"],
        }

    if e["host"] == "other" or e["interface"] != "supported":
        return result(
            "unsupported_or_unknown_host",
            "inspect_host",
            "Check the host version and supported plugin/MCP interfaces; do not guess commands.",
        )
    installed = e["installation"]
    if installed == "unknown":
        return result(
            "installation_unknown",
            "inspect_installation",
            "Inspect the client's plugin/server listing without reading credentials.",
        )
    if installed in ("absent", "failed", "never_started"):
        if installed == "failed" and not retry:
            return result(
                "installation_failed",
                "resolve_installation",
                "Resolve the reported installation failure, then explicitly retry.",
            )
        if installed == "never_started" and not retry:
            return result(
                "installation_never_started",
                "resolve_installation",
                "The claimed install attempt was confirmed never started; retry explicitly to issue a fresh attempt. Absence alone is not confirmation.",
            )
        if journal["install_claimed"] and not (
            installed in ("failed", "never_started")
            and retry
            and e["install_attempt"] == journal["install_attempt"]
        ):
            return result(
                "installation_pending",
                "inspect_installation",
                "Recheck the existing install attempt; do not add another entry.",
            )
        journal["install_claimed"] = True
        journal["install_attempt"] += 1
        return result(
            "installation",
            "install_plugin",
            "Add only the missing marketplace/plugin using the supported host interface, preserving required approvals.",
        )
    # The client shows a plugin or direct connection. A claimed attempt settles
    # only when the observation names the attempt this journal returned; a stale
    # success must not release a newer pending claim.
    if journal["install_claimed"]:
        if e["install_attempt"] != journal["install_attempt"]:
            return result(
                "installation_pending",
                "inspect_installation",
                "Recheck the existing install attempt; do not add another entry.",
            )
        journal["install_claimed"] = False
    if e["login"] == "pending":
        journal["login_claimed"] = True
        return result(
            "waiting_for_sign_in",
            "wait_for_user",
            "Wait for the same client-owned login; the user completes sign-in and consent. Do not start another flow.",
        )
    auth = e["authentication"]
    if auth == "unknown":
        return result(
            "authentication_unknown",
            "inspect_authentication",
            "Check client authentication status; browser launch and OAuth support alone do not prove login.",
        )
    if auth == "missing":
        ended = e["login"] in ("cancelled", "failed", "timed_out", "never_started")
        if ended and not retry:
            if e["login"] == "never_started":
                return result(
                    "login_never_started",
                    "resolve_login",
                    "The claimed login attempt was confirmed never started; retry explicitly to issue a fresh attempt. An idle status or a lost handle alone is not confirmation.",
                )
            return result(
                "login_" + e["login"],
                "resolve_login",
                "Report the ended attempt. Retry only after checking authentication again and an explicit request to resume.",
            )
        if journal["login_claimed"] and not (
            ended and retry and e["login_attempt"] == journal["login_attempt"]
        ):
            return result(
                "login_result_unknown",
                "inspect_login",
                "Resolve the previously claimed login attempt; do not start another flow.",
            )
        journal["login_claimed"] = True
        journal["login_attempt"] += 1
        if e["host"] == "claude_code":
            return result(
                "waiting_for_sign_in",
                "user_authenticate",
                "Run /mcp, choose tahoe-public, and Authenticate in Claude Code; the user completes sign-in.",
            )
        return result(
            "authentication",
            "start_client_login",
            "Run codex mcp login tahoe-public in a persistent terminal. Preserve host approvals; the client opens its browser.",
        )
    journal["login_claimed"] = False
    if e["session"] == "reload_required":
        return result(
            "session_reload",
            "reload_session",
            "Start a new Codex session or restart Claude Code, then resume preflight with fresh observations.",
        )
    if e["session"] == "unknown":
        return result(
            "session_unknown",
            "inspect_session",
            "Check whether this session loaded the authenticated connection.",
        )
    if e["tools"] != "available":
        return result(
            "tools_missing",
            "inspect_tools",
            "Check tahoe-public tools in this client; reload once if needed, then diagnose connection/service errors. Do not reinstall or repeat OAuth.",
        )
    status = e["witness_status"]
    if status == "succeeded":
        w = e.get("witness")
        if (
            w
            and w["session_tag"] == e["session_tag"]
            and w["ok"] is True
            and w["status"] == "ok"
            and w["release_count"] > 0
        ):
            return result(
                "ready",
                "none",
                "The current client's read-only list_releases call succeeded; record host/server versions and release identifiers separately.",
            )
        return result(
            "witness_unverified",
            "inspect_witness",
            "Readiness needs a successful list_releases response from this same session and client connection.",
        )
    if status == "unauthorized":
        return result(
            "authentication_rejected",
            "inspect_authentication",
            "Recheck client authentication after the rejected tool call; do not automatically restart OAuth.",
        )
    if status != "not_run" and not retry:
        return result(
            "witness_" + status,
            "resolve_witness",
            "Report the tool failure, respect service retry hints, and resume only after resolving it.",
        )
    if journal["witness_session"] != e["session_tag"]:
        journal["witness_session"] = e["session_tag"]
        journal["witness_attempts"] = 0
    attempts = journal["witness_attempts"]
    if attempts >= 2 or (attempts and not (status != "not_run" and retry)):
        return result(
            "witness_pending_or_exhausted",
            "inspect_witness",
            "Inspect the previous call result; at most one explicit retry per session is allowed. Do not submit duplicate calls.",
        )
    journal["witness_attempts"] += 1
    return result(
        "read_only_witness",
        "call_list_releases",
        "Call list_releases once through this session's tahoe-public MCP connection, with the client's bounded timeout; normalize only the documented witness fields.",
    )


@contextmanager
def locked_journal(path):
    # The lock is intentionally not auto-expired: age cannot prove OAuth ended.
    lock = path.with_name(path.name + ".lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def run(evidence, path, retry=False):
    validate(evidence)
    if path.is_symlink():
        raise InvalidEvidence("Journal must be a regular local file, not a symlink.")
    with locked_journal(path):
        if path.exists():
            if path.stat().st_size > MAX_BYTES:
                raise InvalidEvidence(
                    "Journal is too large; preserve it and inspect setup state."
                )
            journal = json.loads(path.read_text())
        else:
            journal = fresh_journal(evidence["host"])
        result = step(evidence, journal, retry)
        temp = path.with_name(path.name + ".tmp")
        # Exclusive creation avoids following an existing temporary-file symlink.
        fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(journal, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--journal",
        type=Path,
        required=True,
        help="one private local journal per host/connection; reuse it across sessions",
    )
    parser.add_argument(
        "--retry",
        action="store_true",
        help="explicit resume after a confirmed ended failure or a confirmed never-started attempt, never while pending",
    )
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise InvalidEvidence("Observation exceeds the size limit.")
        result = run(json.loads(raw), args.journal, args.retry)
    except FileExistsError:
        result = {
            "stage": "busy_or_interrupted",
            "ready": False,
            "action": "inspect_attempt",
            "next_action": "Another preflight owns the journal, or its write was interrupted. Confirm it ended before removing its lock/temporary file; never start another OAuth flow.",
        }
    except (ValueError, OSError):
        # Never echo raw input, paths, exception messages or client output.
        result = {
            "stage": "unknown",
            "ready": False,
            "action": "inspect_evidence",
            "next_action": "Check sanitized evidence and the journal's availability. No setup action was issued.",
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
