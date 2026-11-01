"""Offline tests for the local MCP proxy. No network and no eval runner.

The upstream in these tests is a localhost server. Recordings are synthetic.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from scripts import common
from scripts import eval_proxy
from scripts.eval_pack import EvalError, retarget_plugin_copy_local

FAKE_BEARER = "synthetic-bearer-for-tests"


class _Fake(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003
        return

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else b""
        self.server.seen.append(
            {"authorization": self.headers.get("Authorization"), "body": body}
        )
        status, content_type, payload = self.server.script.pop(0)
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Mcp-Session-Id", "upstream-session")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _fake(script: list) -> tuple[ThreadingHTTPServer, str]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Fake)
    httpd.seen = []
    httpd.script = script
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/mcp"
    return httpd, url


def _token(path: Path, mode: int = 0o600, payload: dict | None = None) -> Path:
    path.write_text(
        json.dumps({"access_token": FAKE_BEARER} if payload is None else payload),
        encoding="utf-8",
    )
    path.chmod(mode)
    return path


def _rpc(request_id: int, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _sse(payload: dict) -> bytes:
    return f"event: message\ndata: {json.dumps(payload)}\n\n".encode()


def _post(port: int, message: dict, method: str = "POST", path: str = "/mcp"):
    import http.client

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    raw = json.dumps(message).encode() if method == "POST" else b""
    conn.request(
        method,
        path,
        body=raw if method == "POST" else None,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    response = conn.getresponse()
    body = response.read()
    status = response.status
    conn.close()
    return status, body


def _start_record(tmp_path: Path, upstream: str) -> tuple[subprocess.Popen[str], int]:
    port_file = tmp_path / "port"
    proc = subprocess.Popen(
        [
            sys.executable,
            str(common.REPO_ROOT / "scripts" / "eval_proxy.py"),
            "record",
            "--upstream",
            upstream,
            "--token-file",
            str(tmp_path / "token.json"),
            "--out",
            str(tmp_path / "out"),
            "--port-file",
            str(port_file),
        ],
        cwd=common.REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    for _ in range(50):
        if port_file.is_file() and port_file.read_text(encoding="utf-8").strip():
            break
        if proc.poll() is not None:
            stdout, stderr = proc.communicate()
            raise AssertionError(f"proxy exited {proc.returncode}: {stderr} {stdout}")
        threading.Event().wait(0.05)
    else:
        proc.kill()
        raise AssertionError("proxy did not write a port")
    return proc, int(port_file.read_text(encoding="utf-8"))


def _stop(proc: subprocess.Popen[str]) -> tuple[str, str]:
    proc.terminate()
    try:
        return proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        return proc.communicate()


def _read_recording(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "out" / "responses.json").read_text(encoding="utf-8"))


def test_record_keeps_one_key_for_intent_and_replaces_only_a_pending_result(tmp_path):
    """JSON and SSE replies are stored. The bearer is sent and not recorded."""
    final = {"status": "ready", "value": "synthetic-final"}
    pending = {"status": "pending", "value": "synthetic-pending"}
    later = {"status": "ready", "value": "synthetic-second"}
    calls = [
        (200, "application/json", _rpc(1, {"protocolVersion": "synthetic"})),
        (200, "text/event-stream", _sse(_rpc(2, {"tools": [{"name": "health"}]}))),
        (200, "application/json", _rpc(3, {"structuredContent": pending})),
        (200, "application/json", _rpc(4, {"structuredContent": final})),
        (200, "application/json", _rpc(5, {"structuredContent": pending})),
        (200, "application/json", _rpc(6, {"structuredContent": later})),
    ]
    fake, url = _fake(calls)
    _token(tmp_path / "token.json")
    proc, port = _start_record(tmp_path, url)
    try:
        _post(port, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        _post(port, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        for index, intent in enumerate(("one", "two", "three", "four"), start=3):
            _post(
                port,
                {
                    "jsonrpc": "2.0",
                    "id": index,
                    "method": "tools/call",
                    "params": {
                        "name": "health",
                        "arguments": {
                            "intent": intent,
                            "model": "synthetic-model",
                            "result_handle": None,
                            "echo": "same",
                        },
                    },
                },
            )
    finally:
        stdout, stderr = _stop(proc)
        fake.shutdown()
        fake.server_close()
    blob = (tmp_path / "out" / "responses.json").read_text(encoding="utf-8")
    assert FAKE_BEARER not in blob
    assert FAKE_BEARER not in stdout
    assert FAKE_BEARER not in stderr
    assert FAKE_BEARER not in (tmp_path / "port").read_text(encoding="utf-8")
    assert [item["authorization"] for item in fake.seen] == [f"Bearer {FAKE_BEARER}"] * 6
    forwarded = json.loads(fake.seen[2]["body"])
    assert forwarded["params"]["arguments"]["intent"] == "one"
    recorded = _read_recording(tmp_path)
    assert recorded["initialize"] == {"protocolVersion": "synthetic"}
    assert recorded["tools/list"] == {"tools": [{"name": "health"}]}
    assert list(recorded["calls"]) == ['health|{"echo":"same"}']
    assert recorded["calls"]['health|{"echo":"same"}']["structuredContent"] == final
    assert recorded["conflicts"] == {'health|{"echo":"same"}': 1}
    assert recorded["disclosure_hits"] == []


def test_record_lists_a_disclosure_hit_and_still_returns_the_upstream_body(tmp_path):
    planted = "D" + "94"
    fake, url = _fake(
        [(200, "application/json", _rpc(1, {"structuredContent": {"note": planted}}))]
    )
    _token(tmp_path / "token.json")
    proc, port = _start_record(tmp_path, url)
    try:
        status, body = _post(
            port,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "health", "arguments": {}},
            },
        )
    finally:
        _stop(proc)
        fake.shutdown()
        fake.server_close()
    assert status == 200
    assert planted in body.decode()
    hits = _read_recording(tmp_path)["disclosure_hits"]
    assert hits and hits[0]["patterns"] == ["internal_ref"]
    assert planted not in json.dumps(hits)


@pytest.fixture
def no_serve(monkeypatch):
    """Record whether `main` reached the server. A refusal must return first.

    Without this stub a missing guard would start `serve_forever` in-process
    and hang the run instead of failing it.
    """
    served: list[bool] = []
    monkeypatch.setattr(eval_proxy, "_serve", lambda state, port_file: served.append(True))
    return served


def test_record_refuses_a_non_loopback_http_upstream_before_binding(tmp_path, no_serve):
    port_file = tmp_path / "port"
    code = eval_proxy.main(
        [
            "record",
            "--upstream",
            "http://example.test/mcp",
            "--token-file",
            str(_token(tmp_path / "token.json")),
            "--out",
            str(tmp_path / "out"),
            "--port-file",
            str(port_file),
        ]
    )
    assert code == 2
    assert not port_file.exists()
    assert no_serve == []


@pytest.mark.parametrize(
    "url",
    ["https://user:pw@example.test/mcp", "https://example.test/mcp?q=1"],
)
def test_record_refuses_userinfo_or_a_query_before_binding(tmp_path, no_serve, url):
    port_file = tmp_path / "port"
    code = eval_proxy.main(
        [
            "record",
            "--upstream",
            url,
            "--token-file",
            str(_token(tmp_path / "token.json")),
            "--out",
            str(tmp_path / "out"),
            "--port-file",
            str(port_file),
        ]
    )
    assert code == 2
    assert not port_file.exists()
    assert no_serve == []


def test_record_refuses_a_token_file_that_is_not_mode_0600(tmp_path, no_serve):
    port_file = tmp_path / "port"
    code = eval_proxy.main(
        [
            "record",
            "--upstream",
            "https://example.test/mcp",
            "--token-file",
            str(_token(tmp_path / "token.json", mode=0o644)),
            "--out",
            str(tmp_path / "out"),
            "--port-file",
            str(port_file),
        ]
    )
    assert code == 2
    assert not port_file.exists()
    assert no_serve == []


def test_record_refuses_a_token_file_without_access_token(tmp_path, no_serve):
    port_file = tmp_path / "port"
    code = eval_proxy.main(
        [
            "record",
            "--upstream",
            "https://example.test/mcp",
            "--token-file",
            str(_token(tmp_path / "token.json", payload={"token": "nope"})),
            "--out",
            str(tmp_path / "out"),
            "--port-file",
            str(port_file),
        ]
    )
    assert code == 2
    assert not port_file.exists()
    assert no_serve == []


def _replay_recording(tmp_path: Path, calls: dict) -> Path:
    directory = tmp_path / "recording"
    directory.mkdir(parents=True)
    payload = {
        "format": "eval-recording/1",
        "initialize": {"protocolVersion": "synthetic"},
        "tools/list": {"tools": [{"name": "health"}]},
        "calls": calls,
        "conflicts": {},
        "disclosure_hits": [],
    }
    (directory / "responses.json").write_text(json.dumps(payload), encoding="utf-8")
    return directory


def _start_replay(directory: Path, misses: Path):
    state = eval_proxy._State("replay")
    payload = json.loads((directory / "responses.json").read_text(encoding="utf-8"))
    state.initialize = payload["initialize"]
    state.tools = payload["tools/list"]
    state.calls = payload["calls"]
    state.misses = misses
    misses.touch()
    httpd = eval_proxy._server(state)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def test_replay_returns_the_recorded_result_for_a_different_intent(tmp_path):
    stored = {"structuredContent": {"ok": True, "label": "synthetic-replay"}}
    key = eval_proxy.canonical_key("health", {"echo": "same"})
    directory = _replay_recording(tmp_path, {key: stored})
    misses = tmp_path / "misses.jsonl"
    httpd = _start_replay(directory, misses)
    try:
        assert httpd.server_address[0] == "127.0.0.1"
        port = httpd.server_address[1]
        status, body = _post(
            port,
            {"jsonrpc": "2.0", "id": 7, "method": "initialize", "params": {}},
        )
        assert status == 200
        assert json.loads(body)["result"]["protocolVersion"] == "synthetic"
        status, body = _post(port, {"jsonrpc": "2.0", "id": 8, "method": "tools/list"})
        assert json.loads(body)["result"]["tools"] == [{"name": "health"}]
        status, body = _post(
            port,
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {
                    "name": "health",
                    "arguments": {"echo": "same", "intent": "other", "model": "other"},
                },
            },
        )
        assert json.loads(body)["result"] == stored
        status, body = _post(
            port,
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {"name": "health", "arguments": {"echo": "missing"}},
            },
        )
        result = json.loads(body)["result"]
        assert result["isError"] is True
        assert "not_recorded" in result["content"][0]["text"]
        logged = json.loads(misses.read_text(encoding="utf-8").splitlines()[0])
        assert logged == {"arguments": {"echo": "missing"}, "tool": "health"}
        status, body = _post(port, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert status == 202
        assert body == b""
        status, body = _post(port, {"jsonrpc": "2.0", "id": 11, "method": "unknown/method"})
        assert json.loads(body)["error"]["code"] == -32601
        status, _body = _post(port, {}, method="GET")
        assert status == 405
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_replay_refuses_a_decision_code_or_an_atlas_fragment(tmp_path, no_serve):
    for note in ("D" + "94", "as" + "pian"):
        directory = _replay_recording(
            tmp_path / note,
            {
                "health|{}": {"structuredContent": {"note": note}},
            },
        )
        # directory name with the note may be odd; use a fresh child
        port_file = tmp_path / f"port-{note}"
        code = eval_proxy.main(
            [
                "replay",
                "--recording",
                str(directory),
                "--port-file",
                str(port_file),
                "--misses",
                str(tmp_path / "misses.jsonl"),
            ]
        )
        assert code == 2
        assert not port_file.exists()
        assert no_serve == []


def test_replay_accepts_the_allowlisted_cell_name_and_refuses_another_key(tmp_path, no_serve):
    """``cell_name`` NCI-N87 is exempt. The same text under another key is not."""
    allowed = _replay_recording(
        tmp_path / "allowed",
        {"health|{}": {"structuredContent": {"cell_name": "NCI-N87"}}},
    )
    refused = _replay_recording(
        tmp_path / "refused",
        {"health|{}": {"structuredContent": {"note": "NCI-N87"}}},
    )
    assert eval_proxy._load_replay(allowed)["calls"]
    code = eval_proxy.main(
        [
            "replay",
            "--recording",
            str(refused),
            "--port-file",
            str(tmp_path / "port-no"),
            "--misses",
            str(tmp_path / "miss-no"),
        ]
    )
    assert code == 2
    assert not (tmp_path / "port-no").exists()
    assert no_serve == []


def test_retarget_local_sets_the_loopback_url_and_refuses_the_repo_and_bad_ports(tmp_path):
    original = (common.plugin_dir() / "mcp.json").read_text(encoding="utf-8")
    copy = tmp_path / "plugin"
    (copy / ".claude-plugin").mkdir(parents=True)
    manifest = {
        "mcpServers": {
            "tahoe-public": {
                "type": "http",
                "url": "https://example.test/original",
                "headers": {"Authorization": "drop-me"},
            }
        }
    }
    for rel in ("mcp.json", ".claude-plugin/plugin.json"):
        (copy / rel).write_text(json.dumps(manifest), encoding="utf-8")
    retarget_plugin_copy_local(copy, 9, repo_plugin=common.plugin_dir())
    written = json.loads((copy / "mcp.json").read_text(encoding="utf-8"))
    assert written["mcpServers"]["tahoe-public"]["url"] == "http://127.0.0.1:9/mcp"
    assert "headers" not in written["mcpServers"]["tahoe-public"]
    with pytest.raises(EvalError, match="repository plugin"):
        retarget_plugin_copy_local(common.plugin_dir(), 9, repo_plugin=common.plugin_dir())
    for port in (0, 70000):
        with pytest.raises(EvalError, match="port"):
            retarget_plugin_copy_local(copy, port, repo_plugin=common.plugin_dir())
    assert json.loads((copy / "mcp.json").read_text(encoding="utf-8"))["mcpServers"][
        "tahoe-public"
    ]["url"] == "http://127.0.0.1:9/mcp"
    assert (common.plugin_dir() / "mcp.json").read_text(encoding="utf-8") == original


def _stub_claude(directory: Path) -> None:
    stub = directory / "claude"
    stub.write_text(
        "\n".join(
            (
                "#!/bin/sh",
                "output_dir=",
                "json_path=",
                "prev=",
                'for arg in "$@"; do',
                '  if [ "$prev" = "--output-dir" ]; then output_dir=$arg',
                '  elif [ "$prev" = "--json" ]; then json_path=$arg; fi',
                "  prev=$arg",
                "done",
                'mkdir -p "$output_dir"',
                "printf '%s\\n' '{\"partial\":false,\"cases\":[]}' > \"$output_dir/aggregate-result.json\"",
                "printf '%s\\n' '<html>synthetic report</html>' > \"$output_dir/report.html\"",
                "printf '%s\\n' '{\"partial\":false,\"cases\":[]}' > \"$json_path\"",
                "exit 1",
                "",
            )
        ),
        encoding="utf-8",
    )
    stub.chmod(0o755)


def test_eval_record_exits_2_when_the_upstream_env_is_missing(tmp_path):
    env = os.environ.copy()
    env.pop("EVAL_UPSTREAM_URL", None)
    env.pop("EVAL_TOKEN_FILE", None)
    completed = subprocess.run(
        ["sh", str(common.REPO_ROOT / "scripts" / "eval_record.sh"), str(tmp_path / "run")],
        cwd=common.REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert not (common.plugin_dir() / "evals").exists()


def test_failing_record_run_still_copies_live_evidence(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _stub_claude(bindir)
    token = _token(tmp_path / "token.json")
    run_dir = tmp_path / "run"
    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["EVAL_UPSTREAM_URL"] = "https://example.test/mcp"
    env["EVAL_TOKEN_FILE"] = str(token)
    env.setdefault("UV_CACHE_DIR", "/tmp/uv-cache")
    completed = subprocess.run(
        ["sh", str(common.REPO_ROOT / "scripts" / "eval_record.sh"), str(run_dir)],
        cwd=common.REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1, completed.stderr
    assert FAKE_BEARER not in completed.stdout
    assert FAKE_BEARER not in completed.stderr
    assert "synthetic report" in (run_dir / "eval-live-report.html").read_text(encoding="utf-8")
    assert (run_dir / "eval-live-aggregate-result.json").is_file()
    assert (run_dir / "eval-live-result.json").is_file()
    assert (run_dir / "eval-record.json").is_file()
    recorded = (run_dir / "eval-recording" / "responses.json").read_text(encoding="utf-8")
    assert FAKE_BEARER not in recorded
    assert not (common.plugin_dir() / "evals").exists()


def test_a_none_argument_maps_to_the_same_key_as_an_omitted_one():
    """The agent may send an optional argument as null or leave it out; both replay
    the same recorded call."""
    assert eval_proxy.canonical_key("get_pathway_scores", {"drug": ["X"], "dose": None}) == (
        eval_proxy.canonical_key("get_pathway_scores", {"drug": ["X"]})
    )
    assert eval_proxy.canonical_key("get_pathway_scores", {"drug": ["X"], "dose": 0.5}) != (
        eval_proxy.canonical_key("get_pathway_scores", {"drug": ["X"]})
    )
