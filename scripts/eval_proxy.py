"""Local MCP proxy for record and replay of plugin eval calls.

Stdlib only. The process binds ``127.0.0.1`` and writes the chosen port to
``--port-file``. The bearer token is added to upstream requests and is never
written to the recording, stdout, or stderr.

``record`` forwards each POST to the upstream and stores ``tools/call``
results. ``replay`` serves that recording and does not use the network.
Loopback ``http://127.0.0.1`` or ``http://localhost`` is accepted as an
upstream so an offline test can stand in for the service. Every other
upstream must be ``https`` with a host and no userinfo, query, or fragment.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.eval_pack import (  # noqa: E402
    RECORDING_FORMAT,
    EvalError,
    recording_disclosure_hits,
    tool_body,
)

_DROPPED = frozenset({"intent", "model", "result_handle"})
_FORWARD = ("Content-Type", "Accept", "Mcp-Session-Id", "Mcp-Protocol-Version")
_BIND = "127.0.0.1"


class ProxyError(Exception):
    """The proxy cannot start. The message never contains a token."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Leave a redirect as the upstream status instead of following it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def canonical_arguments(arguments: object) -> dict[str, Any]:
    """Arguments that identify a call.

    ``intent``, ``model``, and ``result_handle`` vary between runs and do not
    change the result. A key whose value is ``None`` is omitted too.
    """
    if not isinstance(arguments, dict):
        return {}
    return {
        key: value
        for key, value in arguments.items()
        if key not in _DROPPED and value is not None
    }


def canonical_key(tool: str, arguments: object) -> str:
    """Tool name plus canonical JSON arguments."""
    return tool + "|" + json.dumps(
        canonical_arguments(arguments), sort_keys=True, separators=(",", ":")
    )


def validate_upstream(url: str) -> None:
    """Refuse a URL the record mode must not call."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ProxyError("upstream must not carry credentials, a query, or a fragment")
    host = parsed.hostname or ""
    if parsed.scheme == "https" and host:
        return
    if parsed.scheme == "http" and host in {"127.0.0.1", "localhost"}:
        return
    raise ProxyError("upstream must be https")


def load_token(path: Path) -> str:
    """Read ``access_token`` from a mode-0600 JSON file. Exit-class errors only."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ProxyError("token file must be a regular file")
    if (path.stat().st_mode & 0o777) != 0o600:
        raise ProxyError("token file mode must be 0600")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProxyError("token file must be JSON") from exc
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not isinstance(token, str) or token == "":
        raise ProxyError("token file has no access_token")
    return token


def _is_pending(result: object) -> bool:
    body = tool_body(result)
    return isinstance(body, dict) and body.get("status") == "pending"


def _parse_reply(content_type: str, body: bytes) -> object | None:
    if "text/event-stream" in content_type.lower():
        data = [
            line[5:].strip()
            for line in body.decode("utf-8", "replace").splitlines()
            if line.startswith("data:")
        ]
        if not data:
            return None
        try:
            return json.loads(data[-1])
        except json.JSONDecodeError:
            return None
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


class _State:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.lock = threading.Lock()
        self.token = ""
        self.upstream = ""
        self.opener: urllib.request.OpenerDirector | None = None
        self.out: Path | None = None
        self.misses: Path | None = None
        self.initialize: object = None
        self.tools: object = None
        self.calls: dict[str, object] = {}
        self.conflicts: dict[str, int] = {}
        self.seen_initialize = False
        self.seen_tools = False

    def recording(self) -> dict[str, object]:
        return {
            "format": RECORDING_FORMAT,
            "initialize": self.initialize,
            "tools/list": self.tools,
            "calls": self.calls,
            "conflicts": self.conflicts,
            "disclosure_hits": recording_disclosure_hits(self._scan_view()),
        }

    def _scan_view(self) -> dict[str, object]:
        return {
            "initialize": self.initialize,
            "tools/list": self.tools,
            "calls": self.calls,
        }

    def write(self) -> None:
        if self.out is None:
            return
        self.out.parent.mkdir(parents=True, exist_ok=True)
        payload = self.recording()
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        temporary = self.out.with_suffix(self.out.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, self.out)

    def note_reply(self, request: object, reply: object) -> None:
        if not isinstance(request, dict) or not isinstance(reply, dict):
            return
        if "error" in reply or "result" not in reply:
            return
        method = request.get("method")
        result = reply["result"]
        if method == "initialize" and not self.seen_initialize:
            self.initialize = result
            self.seen_initialize = True
            self.write()
        elif method == "tools/list" and not self.seen_tools:
            self.tools = result
            self.seen_tools = True
            self.write()
        elif method == "tools/call":
            params = request.get("params") if isinstance(request.get("params"), dict) else {}
            name = params.get("name") if isinstance(params, dict) else None
            if not isinstance(name, str) or not name:
                return
            arguments = params.get("arguments") if isinstance(params, dict) else {}
            key = canonical_key(name, arguments)
            self._store_call(key, result)
            self.write()

    def _store_call(self, key: str, result: object) -> None:
        pending = _is_pending(result)
        stored = self.calls.get(key)
        if stored is None:
            self.calls[key] = result
            return
        if pending:
            return
        if _is_pending(stored):
            self.calls[key] = result
            return
        self.conflicts[key] = self.conflicts.get(key, 0) + 1


def _load_replay(path: Path) -> dict[str, Any]:
    recording = path / "responses.json"
    if not recording.is_file():
        raise ProxyError("recording has no responses.json")
    try:
        payload = json.loads(recording.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProxyError("recording is not JSON") from exc
    if not isinstance(payload, dict) or payload.get("format") != RECORDING_FORMAT:
        raise ProxyError("recording format is wrong")
    if not isinstance(payload.get("initialize"), dict):
        raise ProxyError("recording has no initialize result")
    if not isinstance(payload.get("tools/list"), dict):
        raise ProxyError("recording has no tools/list result")
    if not isinstance(payload.get("calls"), dict):
        raise ProxyError("recording calls are not an object")
    try:
        hits = recording_disclosure_hits(payload)
    except EvalError as exc:
        raise ProxyError("disclosure allowlist is malformed") from exc
    if hits:
        raise ProxyError("recording failed the disclosure gate")
    return payload


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: object | None) -> None:
    body = b"" if payload is None else json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    if payload is not None:
        handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    if body:
        handler.wfile.write(body)


def _rpc(request_id: object, result: object) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _rpc_error(request_id: object, code: int, message: str) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def _state(self) -> _State:
        return self.server.state  # type: ignore[attr-defined]

    def _reject_method(self) -> None:
        if urllib.parse.urlsplit(self.path).path != "/mcp":
            self.send_error(404)
            return
        self.send_response(405)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        self._reject_method()

    def do_DELETE(self) -> None:  # noqa: N802
        self._reject_method()

    def do_PUT(self) -> None:  # noqa: N802
        self._reject_method()

    def do_POST(self) -> None:  # noqa: N802
        if urllib.parse.urlsplit(self.path).path != "/mcp":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else b""
        if self._state().mode == "record":
            self._record(body)
        else:
            self._replay(body)

    def _record(self, body: bytes) -> None:
        state = self._state()
        headers = {name: self.headers[name] for name in _FORWARD if self.headers.get(name)}
        headers["Authorization"] = f"Bearer {state.token}"
        request = urllib.request.Request(
            state.upstream, data=body, method="POST", headers=headers
        )
        assert state.opener is not None
        try:
            with state.opener.open(request, timeout=120) as response:
                status, reply_headers, reply_body = (
                    response.status,
                    response.headers,
                    response.read(),
                )
        except urllib.error.HTTPError as exc:
            status, reply_headers, reply_body = exc.code, exc.headers, exc.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            _json_response(self, 502, {"error": "upstream failed"})
            return
        try:
            message = json.loads(body) if body else None
            reply = _parse_reply(reply_headers.get("Content-Type", ""), reply_body)
            with state.lock:
                state.note_reply(message, reply)
        except (json.JSONDecodeError, OSError, EvalError, TypeError, ValueError):
            pass
        self.send_response(status)
        for name in ("Content-Type", "Mcp-Session-Id"):
            value = reply_headers.get(name)
            if value:
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(reply_body)))
        self.end_headers()
        self.wfile.write(reply_body)

    def _replay(self, body: bytes) -> None:
        state = self._state()
        try:
            message = json.loads(body) if body else None
        except json.JSONDecodeError:
            _json_response(self, 400, _rpc_error(None, -32700, "parse error"))
            return
        if not isinstance(message, dict) or not isinstance(message.get("method"), str):
            _json_response(self, 400, _rpc_error(None, -32600, "invalid request"))
            return
        if "id" not in message:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        method = message["method"]
        request_id = message["id"]
        if method == "ping":
            _json_response(self, 200, _rpc(request_id, {}))
            return
        if method == "initialize":
            _json_response(self, 200, _rpc(request_id, state.initialize))
            return
        if method == "tools/list":
            _json_response(self, 200, _rpc(request_id, state.tools))
            return
        if method == "tools/call":
            self._replay_call(message, request_id)
            return
        _json_response(self, 200, _rpc_error(request_id, -32601, "method not found"))

    def _replay_call(self, message: dict, request_id: object) -> None:
        state = self._state()
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        name = params.get("name") if isinstance(params, dict) else ""
        arguments = params.get("arguments") if isinstance(params, dict) else {}
        if not isinstance(name, str):
            name = ""
        key = canonical_key(name, arguments)
        with state.lock:
            stored = state.calls.get(key)
        if stored is None:
            if state.misses is not None:
                line = json.dumps(
                    {"arguments": canonical_arguments(arguments), "tool": name},
                    sort_keys=True,
                )
                with state.lock:
                    with state.misses.open("a", encoding="utf-8") as handle:
                        handle.write(line + "\n")
            _json_response(
                self,
                200,
                _rpc(
                    request_id,
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": '{"ok": false, "error_type": "not_recorded"}',
                            }
                        ],
                        "isError": True,
                    },
                ),
            )
            return
        _json_response(self, 200, _rpc(request_id, stored))


def _server(state: _State) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((_BIND, 0), Handler)
    httpd.state = state  # type: ignore[attr-defined]
    return httpd


def _serve(state: _State, port_file: Path) -> None:
    httpd = _server(state)
    if state.mode == "record":
        with state.lock:
            state.write()
    port_file.parent.mkdir(parents=True, exist_ok=True)
    port_file.write_text(str(httpd.server_address[1]), encoding="utf-8")
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("record")
    record.add_argument("--upstream", required=True)
    record.add_argument("--token-file", required=True, type=Path)
    record.add_argument("--out", required=True, type=Path)
    record.add_argument("--port-file", required=True, type=Path)
    replay = sub.add_parser("replay")
    replay.add_argument("--recording", required=True, type=Path)
    replay.add_argument("--port-file", required=True, type=Path)
    replay.add_argument("--misses", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            validate_upstream(args.upstream)
            token = load_token(args.token_file)
            state = _State("record")
            state.token = token
            state.upstream = args.upstream
            state.out = args.out / "responses.json"
            state.opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}), _NoRedirect()
            )
        else:
            payload = _load_replay(args.recording)
            state = _State("replay")
            state.initialize = payload["initialize"]
            state.tools = payload["tools/list"]
            state.calls = payload["calls"]
            state.misses = args.misses
            state.misses.parent.mkdir(parents=True, exist_ok=True)
            state.misses.touch()
        _serve(state, args.port_file)
    except ProxyError as exc:
        print(f"eval proxy failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
