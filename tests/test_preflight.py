"""Setup transitions, fail-closed readiness, and durable duplicate-action claims."""

import importlib.util
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from scripts import common

SCRIPT = common.REPO_ROOT / "plugins/tara/scripts/preflight.py"
spec = importlib.util.spec_from_file_location("preflight", SCRIPT)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def evidence(**updates):
    value = dict(
        host="codex",
        host_version="0.162.1",
        interface="supported",
        installation="plugin",
        authentication="authenticated",
        login="idle",
        session="current",
        session_tag="session_a",
        tools="available",
        witness_status="not_run",
        install_attempt=0,
        login_attempt=0,
    )
    value.update(updates)
    return value


def witness(**updates):
    value = dict(
        connection="tahoe-public",
        tool="list_releases",
        transport="client_mcp",
        session_tag="session_a",
        ok=True,
        status="ok",
        server_version="0.3.29",
        release_count=1,
    )
    value.update(updates)
    return value


def test_fresh_install_login_reload_and_same_client_witness(tmp_path):
    journal = tmp_path / "state.json"
    e = evidence(
        installation="absent",
        authentication="missing",
        tools="missing",
        session="unknown",
    )
    install = p.run(e, journal)
    assert install["action"] == "install_plugin"
    assert p.run(e, journal)["action"] == "inspect_installation"
    # The observation settling the claim names the attempt the journal returned.
    e.update(installation="plugin", install_attempt=install["install_attempt"])
    started = p.run(e, journal)
    assert started["action"] == "start_client_login"
    assert started["login_attempt"] == 1
    assert p.run(e, journal)["action"] == "inspect_login"
    e.update(login="pending")
    assert p.run(e, journal, retry=True)["action"] == "wait_for_user"
    e.update(login="idle", authentication="authenticated", session="reload_required")
    assert p.run(e, journal)["action"] == "reload_session"
    e.update(session="current", tools="available")
    assert p.run(e, journal)["action"] == "call_list_releases"
    e.update(witness_status="succeeded", witness=witness())
    assert p.run(e, journal)["ready"] is True
    assert "witness" not in json.loads(journal.read_text())
    e.update(session_tag="session_b")
    assert p.run(e, journal)["ready"] is False


@pytest.mark.parametrize(
    "updates,stage",
    [
        ({"host": "other"}, "unsupported_or_unknown_host"),
        ({"interface": "unsupported"}, "unsupported_or_unknown_host"),
        ({"interface": "unknown"}, "unsupported_or_unknown_host"),
        ({"installation": "unknown"}, "installation_unknown"),
        ({"authentication": "unknown"}, "authentication_unknown"),
        ({"login": "pending"}, "waiting_for_sign_in"),
        ({"session": "reload_required"}, "session_reload"),
        ({"session": "unknown"}, "session_unknown"),
        ({"tools": "missing"}, "tools_missing"),
        ({"tools": "unknown"}, "tools_missing"),
        ({"witness_status": "succeeded"}, "witness_unverified"),
        ({"witness_status": "failed"}, "witness_failed"),
        ({"witness_status": "unavailable"}, "witness_unavailable"),
        ({"witness_status": "timed_out"}, "witness_timed_out"),
        ({"witness_status": "unauthorized"}, "authentication_rejected"),
    ],
)
def test_incomplete_stages(updates, stage):
    # Every incomplete stage stays incomplete even if other fields look healthy.
    e = evidence(**updates)
    result = p.step(e, p.fresh_journal(e["host"]))
    assert result["stage"] == stage
    assert result["ready"] is False


@pytest.mark.parametrize("state", ["cancelled", "failed", "timed_out"])
def test_ended_login_requires_explicit_resume_and_current_attempt(tmp_path, state):
    path = tmp_path / "state.json"
    e = evidence(authentication="missing")
    first = p.run(e, path)
    e.update(login=state, login_attempt=first["login_attempt"])
    assert p.run(e, path)["stage"] == "login_" + state
    second = p.run(e, path, retry=True)
    assert second["action"] == "start_client_login"
    assert second["login_attempt"] == 2
    # The same stale failure cannot launch a third login while attempt 2 waits.
    assert p.run(e, path, retry=True)["action"] == "inspect_login"


def test_failed_install_cannot_replay_stale_retry(tmp_path):
    path = tmp_path / "state.json"
    e = evidence(installation="absent")
    first = p.run(e, path)
    e.update(installation="failed", install_attempt=first["install_attempt"])
    assert p.run(e, path)["stage"] == "installation_failed"
    assert p.run(e, path, retry=True)["action"] == "install_plugin"
    assert p.run(e, path, retry=True)["action"] == "inspect_installation"


def test_claude_hands_off_to_supported_user_action(tmp_path):
    path = tmp_path / "state.json"
    e = evidence(host="claude_code", host_version="2.0.0", authentication="missing")
    result = p.run(e, path)
    assert result["action"] == "user_authenticate"
    assert "/mcp" in result["next_action"]
    assert p.run(e, path)["action"] == "inspect_login"


@pytest.mark.parametrize("installation", ["plugin", "direct"])
def test_existing_authenticated_connection_skips_install_and_login(
    tmp_path, installation
):
    result = p.run(evidence(installation=installation), tmp_path / "state.json")
    assert result["action"] == "call_list_releases"
    assert result["install_attempt"] == result["login_attempt"] == 0


@pytest.mark.parametrize(
    "updates",
    [
        {"ok": False},
        {"status": "error"},
        {"release_count": 0},
        {"session_tag": "old_session"},
    ],
)
def test_unsuccessful_or_stale_witness_is_never_ready(updates):
    e = evidence(witness_status="succeeded", witness=witness(**updates))
    assert p.step(e, p.fresh_journal("codex"))["ready"] is False


@pytest.mark.parametrize(
    "updates",
    [
        {"transport": "http"},
        {"connection": "another-server"},
        {"tool": "health"},
        {"ok": 1},
        {"release_count": True},
        {"authorization": "secret"},
    ],
)
def test_wrong_connection_http_or_secret_fields_are_rejected(updates):
    with pytest.raises(p.InvalidEvidence):
        p.validate(evidence(witness_status="succeeded", witness=witness(**updates)))


def test_witness_is_bounded_and_not_repeated_while_pending(tmp_path):
    path = tmp_path / "state.json"
    e = evidence()
    assert p.run(e, path)["action"] == "call_list_releases"
    assert p.run(e, path, retry=True)["action"] == "inspect_witness"
    e.update(witness_status="timed_out")
    assert p.run(e, path, retry=True)["action"] == "call_list_releases"
    assert p.run(e, path, retry=True)["action"] == "inspect_witness"


def test_parallel_invocations_claim_only_one_login(tmp_path):
    path = tmp_path / "state.json"

    def invoke(_):
        try:
            return p.run(evidence(authentication="missing"), path)["action"]
        except FileExistsError:
            return "busy"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(invoke, range(8)))
    assert results.count("start_client_login") == 1


def test_interrupted_lock_is_not_expired_or_overridden(tmp_path):
    path = tmp_path / "state.json"
    lock = tmp_path / "state.json.lock"
    lock.touch()
    with pytest.raises(FileExistsError):
        p.run(evidence(authentication="missing"), path, retry=True)
    assert lock.exists()


def test_cli_never_echoes_rejected_input(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--journal", str(tmp_path / "state.json")],
        input=json.dumps(evidence(**{"to" + "ken": "DO_NOT_ECHO_THIS"})),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "DO_NOT_ECHO_THIS" not in result.stdout + result.stderr
    assert json.loads(result.stdout)["ready"] is False
    assert not (tmp_path / "state.json").exists()


def test_journal_is_private_and_never_stores_tool_response(tmp_path):
    path = tmp_path / "state.json"
    p.run(evidence(witness_status="succeeded", witness=witness()), path)
    assert path.stat().st_mode & 0o777 == 0o600
    saved = path.read_text()
    assert "server_version" not in saved
    assert "release_count" not in saved
    assert "ready" not in saved


def test_corrupt_journal_and_symlink_fail_closed(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{}")
    with pytest.raises(p.InvalidEvidence):
        p.run(evidence(), path)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(p.InvalidEvidence):
        p.run(evidence(), link)


def test_successful_install_settles_claim_and_later_removal_reinstalls(tmp_path):
    path = tmp_path / "state.json"
    e = evidence(
        installation="absent",
        authentication="missing",
        tools="missing",
        session="unknown",
    )
    first = p.run(e, path)
    assert first["action"] == "install_plugin"
    # The claimed attempt is observed installed, echoing its attempt number.
    e.update(installation="plugin", install_attempt=first["install_attempt"])
    p.run(e, path)
    assert json.loads(path.read_text())["install_claimed"] is False
    # Months later the plugin is really removed: a fresh claim must be possible.
    e.update(installation="absent", install_attempt=0)
    second = p.run(e, path)
    assert second["action"] == "install_plugin"
    assert second["install_attempt"] == first["install_attempt"] + 1
    assert p.run(e, path)["action"] == "inspect_installation"


def test_stale_install_success_or_failure_keeps_the_newer_claim(tmp_path):
    path = tmp_path / "state.json"
    e = evidence(
        installation="absent",
        authentication="missing",
        tools="missing",
        session="unknown",
    )
    first = p.run(e, path)
    e.update(installation="plugin", install_attempt=first["install_attempt"])
    p.run(e, path)
    e.update(installation="absent")
    second = p.run(e, path)
    assert second["action"] == "install_plugin"
    # A stale success echo for the settled attempt must not release attempt 2.
    e.update(installation="plugin", install_attempt=first["install_attempt"])
    stale = p.run(e, path)
    assert stale["stage"] == "installation_pending"
    assert stale["ready"] is False
    saved = json.loads(path.read_text())
    assert saved["install_claimed"] is True
    assert saved["install_attempt"] == second["install_attempt"]
    # A stale failure echo cannot authorize a third attempt either.
    e.update(installation="failed", install_attempt=first["install_attempt"])
    assert p.run(e, path, retry=True)["action"] == "inspect_installation"
    # The current attempt's own accurate success still settles the claim.
    e.update(installation="plugin", install_attempt=second["install_attempt"])
    p.run(e, path)
    assert json.loads(path.read_text())["install_claimed"] is False


def test_confirmed_never_started_install_recovers_with_matching_retry(tmp_path):
    path = tmp_path / "state.json"
    e = evidence(
        installation="absent",
        authentication="missing",
        tools="missing",
        session="unknown",
    )
    first = p.run(e, path)
    assert first["action"] == "install_plugin"
    # The process died between claim and execution; the host confirms the
    # returned action was never executed. Absence alone never suffices.
    e.update(installation="never_started", install_attempt=0)
    assert p.run(e, path, retry=True)["action"] == "inspect_installation"
    e.update(install_attempt=first["install_attempt"])
    blocked = p.run(e, path)
    assert blocked["stage"] == "installation_never_started"
    assert blocked["ready"] is False
    assert json.loads(path.read_text())["install_claimed"] is True
    recovered = p.run(e, path, retry=True)
    assert recovered["action"] == "install_plugin"
    assert recovered["install_attempt"] == first["install_attempt"] + 1
    # Repeating the same confirmed observation cannot start a third attempt.
    assert p.run(e, path, retry=True)["action"] == "inspect_installation"
    assert (
        json.loads(path.read_text())["install_attempt"]
        == recovered["install_attempt"]
    )


def test_confirmed_never_started_login_recovers_with_matching_retry(tmp_path):
    path = tmp_path / "state.json"
    e = evidence(authentication="missing")
    first = p.run(e, path)
    assert first["action"] == "start_client_login"
    # The claimed login command was never executed; the host confirms it.
    e.update(login="never_started", login_attempt=0)
    assert p.run(e, path, retry=True)["action"] == "inspect_login"
    e.update(login_attempt=first["login_attempt"])
    blocked = p.run(e, path)
    assert blocked["stage"] == "login_never_started"
    assert blocked["ready"] is False
    recovered = p.run(e, path, retry=True)
    assert recovered["action"] == "start_client_login"
    assert recovered["login_attempt"] == first["login_attempt"] + 1
    # A repeated recovery against the old attempt cannot duplicate the flow.
    assert p.run(e, path, retry=True)["action"] == "inspect_login"


def test_adopted_pending_login_recovers_only_with_confirmation(tmp_path):
    path = tmp_path / "state.json"
    e = evidence(authentication="missing", login="pending")
    adopted = p.run(e, path)
    assert adopted["action"] == "wait_for_user"
    assert adopted["login_attempt"] == 0
    # The pending attempt vanishes without a client-confirmed terminal state:
    # idle alone is not evidence it ended, not even with --retry.
    e.update(login="idle")
    assert p.run(e, path)["action"] == "inspect_login"
    assert p.run(e, path, retry=True)["action"] == "inspect_login"
    # Positive confirmation that the attempt never ran releases the claim.
    e.update(login="never_started", login_attempt=adopted["login_attempt"])
    assert p.run(e, path)["stage"] == "login_never_started"
    recovered = p.run(e, path, retry=True)
    assert recovered["action"] == "start_client_login"
    assert recovered["login_attempt"] == 1


def test_vanished_attempt_without_confirmation_stays_blocked(tmp_path):
    # A lost handle, idle/absent status or elapsed time never ends a claim.
    login_path = tmp_path / "login.json"
    e = evidence(authentication="missing")
    p.run(e, login_path)
    e.update(login="idle")
    assert p.run(e, login_path)["action"] == "inspect_login"
    assert p.run(e, login_path, retry=True)["action"] == "inspect_login"
    saved = json.loads(login_path.read_text())
    assert saved["login_claimed"] is True
    assert saved["login_attempt"] == 1

    install_path = tmp_path / "install.json"
    e = evidence(
        installation="absent",
        authentication="missing",
        tools="missing",
        session="unknown",
    )
    p.run(e, install_path)
    assert p.run(e, install_path, retry=True)["action"] == "inspect_installation"
    saved = json.loads(install_path.read_text())
    assert saved["install_claimed"] is True
    assert saved["install_attempt"] == 1


def test_parallel_invocations_claim_only_one_install(tmp_path):
    path = tmp_path / "state.json"

    def invoke(_):
        try:
            return p.run(evidence(installation="absent"), path)["action"]
        except FileExistsError:
            return "busy"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(invoke, range(8)))
    assert results.count("install_plugin") == 1
