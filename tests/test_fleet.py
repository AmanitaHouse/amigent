import http.client
import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

from amigent import fleet, webserver
from amigent.amigactl import AmigaError, ExecResult


class FakeCommands:
    """Stands in for a command channel; 'Dead' never answers."""

    log: list = []

    def __init__(self, host, ctl_port=6800, screen_port=6801):
        self.host = host

    def exec(self, command, cd=None, timeout=None):
        if self.host == "Dead":
            raise AmigaError("cannot reach amigentd")
        FakeCommands.log.append((self.host, command))
        return ExecResult(0 if command != "Fail" else 10, f"{self.host}: {command}\n")

    def stat(self, path):
        return {"type": "file"}

    def flush(self, volumes):
        FakeCommands.log.append((self.host, "flush " + " ".join(volumes)))

    def close(self):
        pass


@pytest.fixture(autouse=True)
def fleet_lifecycle(monkeypatch):
    """Prevent real LAN probes from _watch and close every Fleet started in tests."""
    created: list[fleet.Fleet] = []
    original_init = fleet.Fleet.__init__

    def fake_greet(*args, **kwargs):
        raise OSError("offline")

    def tracking_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        created.append(self)

    monkeypatch.setattr(fleet.net, "greet", fake_greet)
    monkeypatch.setattr(fleet.tls, "greet", fake_greet)
    monkeypatch.setattr(fleet.Fleet, "__init__", tracking_init)
    try:
        yield created
    finally:
        for instance in reversed(created):
            instance.close()


def make_fleet(monkeypatch, *names):
    FakeCommands.log = []
    monkeypatch.setattr(fleet, "Commands", FakeCommands)
    return fleet.Fleet([{"name": n, "host": f"10.0.0.{i}"} for i, n in enumerate(names, 1)])


def _post(base: str, path: str, body: bytes, token: str | None = None,
          headers: dict[str, str] | None = None) -> tuple[int, bytes]:
    url = f"{base}{path}" + (f"?t={token}" if token is not None else "")
    request = urllib.request.Request(url, data=body, method="POST", headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=10) as reply:
            return reply.status, reply.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _recv_http_response(sock: socket.socket) -> tuple[bytes, bytes]:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    if b"\r\n\r\n" not in data:
        return data, b""
    head, rest = data.split(b"\r\n\r\n", 1)
    length = 0
    for line in head.split(b"\r\n")[1:]:
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1].strip())
    while len(rest) < length:
        chunk = sock.recv(4096)
        if not chunk:
            break
        rest += chunk
    return head, rest


def test_one_command_for_the_whole_fleet(monkeypatch):
    f = make_fleet(monkeypatch, "A500", "A1200", "Dead")
    result = {r["name"]: r for r in f.run("Version")}
    assert result["A500"] == {"id": 0, "name": "A500", "ok": True, "rc": 0, "output": "A500: Version\n"}
    assert result["A1200"]["ok"] and result["A1200"]["rc"] == 0
    assert not result["Dead"]["ok"] and "reach" in result["Dead"]["error"]
    assert [r["name"] for r in f.run("Fail", [1])] == ["A1200"]


def test_restart_writes_the_disks_first(monkeypatch):
    f = make_fleet(monkeypatch, "A1200")
    assert f.restart(0)["ok"]
    assert FakeCommands.log == [("A1200", "flush SYS:"), ("A1200", "Run >NIL: C:Reboot")]


def test_run_needs_the_token_and_one_line(monkeypatch):
    f = make_fleet(monkeypatch, "A1200")
    base = f.start(0).split("?")[0].rstrip("/")

    def post(path, body, token=f.token):
        status, raw = _post(base, path, json.dumps(body).encode(), token=token)
        return status, (json.loads(raw) if status == 200 else None)

    assert post("/api/run", {"command": "Version"}, token="wrong")[0] == 403
    assert post("/api/run", {"command": "Version\nFormat DF0:"})[0] == 400
    status, result = post("/api/run", {"command": "Version"})
    assert status == 200 and result[0]["output"] == "A1200: Version\n"


def test_rejected_post_consumes_bounded_body_before_reply(monkeypatch):
    """Deterministically prove all rejected body bytes are consumed on the stream."""
    f = make_fleet(monkeypatch, "A1200")
    f.start(0)
    conn = http.client.HTTPConnection("127.0.0.1", f.port, timeout=10)
    try:
        conn.request("POST", "/api/run?t=wrong", body=json.dumps({"command": "Version"}).encode())
        r1 = conn.getresponse()
        body1 = r1.read()
        assert r1.status == 403 and body1 == b"forbidden"
        assert FakeCommands.log == []

        # If the 403 left unread body bytes on the socket, this second HTTP/1.1 request fails.
        conn.request("POST", f"/api/run?t={f.token}", body=json.dumps({"command": "Version"}).encode())
        r2 = conn.getresponse()
        body2 = json.loads(r2.read())
        assert r2.status == 200
        assert body2[0]["output"] == "A1200: Version\n"
        assert FakeCommands.log == [("A1200", "Version")]
    finally:
        conn.close()


def test_repeated_wrong_token_posts_return_403_cleanly(monkeypatch):
    f = make_fleet(monkeypatch, "A1200")
    base = f.start(0).split("?")[0].rstrip("/")
    attempts = 200 if sys.platform == "win32" else 50
    counts = {"403": 0, "aborted": 0, "timeout": 0, "other": 0}
    payload = json.dumps({"command": "Version"}).encode()
    for _ in range(attempts):
        request = urllib.request.Request(f"{base}/api/run?t=wrong", data=payload, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as reply:
                counts["other"] += 1
        except urllib.error.HTTPError as e:
            if e.code == 403:
                counts["403"] += 1
            else:
                counts["other"] += 1
        except ConnectionAbortedError:
            counts["aborted"] += 1
        except TimeoutError:
            counts["timeout"] += 1
    assert counts == {"403": attempts, "aborted": 0, "timeout": 0, "other": 0}
    assert FakeCommands.log == []


def test_fleet_auth_and_boundary_cases(monkeypatch):
    f = make_fleet(monkeypatch, "A1200")
    base = f.start(0).split("?")[0].rstrip("/")

    # Missing token and wrong Host header -> 403 without command execution
    assert _post(base, "/api/run", b'{"command":"Version"}')[0] == 403
    assert _post(base, "/api/run", b'{"command":"Version"}', token="")[0] == 403

    with socket.create_connection(("127.0.0.1", f.port), 5) as sock:
        body = b'{"command":"Version"}'
        req = (
            f"POST /api/run?t={f.token} HTTP/1.1\r\n"
            f"Host: evil.example:{f.port}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode() + body
        sock.sendall(req)
        head, resp_body = _recv_http_response(sock)
        assert head.startswith(b"HTTP/1.1 403") and resp_body == b"forbidden"

    # Empty body
    assert _post(base, "/api/run", b"", token="wrong")[0] == 403
    assert _post(base, "/api/run", b"", token=f.token)[0] == 400

    # Malformed JSON & missing command -> 400
    assert _post(base, "/api/run", b"{bad json", token=f.token)[0] == 400
    assert _post(base, "/api/run", b"{}", token=f.token)[0] == 400

    # Unknown restart target and unknown route -> 404
    assert _post(base, "/api/restart/99", b"{}", token=f.token)[0] == 404
    assert _post(base, "/api/unknown", b"{}", token=f.token)[0] == 404

    # Body right at MAX_FLEET_BODY (65536) with wrong token drains cleanly
    pad = "x" * (fleet.MAX_FLEET_BODY - len('{"command":""}'))
    near_limit = f'{{"command":"{pad}"}}'.encode()
    assert len(near_limit) == fleet.MAX_FLEET_BODY
    assert _post(base, "/api/run", near_limit, token="wrong")[0] == 403
    assert FakeCommands.log == []


def test_fleet_oversized_and_malformed_requests_reject_promptly(monkeypatch):
    f = make_fleet(monkeypatch, "A1200")
    f.start(0)

    # Oversized declared body with wrong token: rejected promptly without draining 10 MB
    start = time.monotonic()
    with socket.create_connection(("127.0.0.1", f.port), 5) as sock:
        sock.sendall(
            f"POST /api/run?t=wrong HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{f.port}\r\n"
            f"Content-Length: 10000000\r\n\r\n".encode()
        )
        head, body = _recv_http_response(sock)
        assert head.startswith(b"HTTP/1.1 403")
        assert b"connection: close" in head.lower()
        assert body == b"forbidden"
    assert time.monotonic() - start < 1.0

    # Oversized declared body just above MAX_FLEET_BODY with valid token -> 400 without draining
    with socket.create_connection(("127.0.0.1", f.port), 5) as sock:
        sock.sendall(
            f"POST /api/run?t={f.token} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{f.port}\r\n"
            f"Content-Length: {fleet.MAX_FLEET_BODY + 1}\r\n\r\n".encode()
        )
        head, body = _recv_http_response(sock)
        assert head.startswith(b"HTTP/1.1 400")
        assert b"connection: close" in head.lower()
        assert body == b"bad request"

    # Malformed Content-Length and chunked Transfer-Encoding
    bad_headers = [
        f"Content-Length: -5\r\n",
        f"Content-Length: abc\r\n",
        f"Content-Length: {'9' * 5000}\r\n",
        f"Content-Length: 5\r\nContent-Length: 5\r\n",
        f"Transfer-Encoding: chunked\r\n",
    ]
    for hdr in bad_headers:
        for tok, expect in (("wrong", b"HTTP/1.1 403"), (f.token, b"HTTP/1.1 400")):
            with socket.create_connection(("127.0.0.1", f.port), 5) as sock:
                sock.sendall(
                    f"POST /api/run?t={tok} HTTP/1.1\r\n"
                    f"Host: 127.0.0.1:{f.port}\r\n"
                    f"{hdr}\r\n".encode()
                )
                head, _ = _recv_http_response(sock)
                assert head.startswith(expect), (hdr, tok, head)
                assert b"connection: close" in head.lower()

    assert FakeCommands.log == []


def test_fleet_stalled_and_disconnected_clients_do_not_hang(monkeypatch):
    monkeypatch.setattr(webserver, "DRAIN_TIMEOUT", 0.15)
    monkeypatch.setattr(fleet, "DRAIN_TIMEOUT", 0.15)
    f = make_fleet(monkeypatch, "A1200")
    f.start(0)

    # Stalled wrong-token client declares 1024 bytes, sends 10, then stalls
    t0 = time.monotonic()
    with socket.create_connection(("127.0.0.1", f.port), 5) as sock:
        sock.sendall(
            f"POST /api/run?t=wrong HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{f.port}\r\n"
            f"Content-Length: 1024\r\n\r\n0123456789".encode()
        )
        head, body = _recv_http_response(sock)
        assert head.startswith(b"HTTP/1.1 403")
        assert b"connection: close" in head.lower()
        assert body == b"forbidden"
    assert time.monotonic() - t0 < 1.5

    # Stalled valid-token client times out cleanly with 400
    t1 = time.monotonic()
    with socket.create_connection(("127.0.0.1", f.port), 5) as sock:
        sock.sendall(
            f"POST /api/run?t={f.token} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{f.port}\r\n"
            f"Content-Length: 1024\r\n\r\n{{\"command\":".encode()
        )
        head, _ = _recv_http_response(sock)
        assert head.startswith(b"HTTP/1.1 400")
        assert b"connection: close" in head.lower()
    assert time.monotonic() - t1 < 1.5

    # Client sends partial body and shuts down write half immediately -> no timeout wait
    t2 = time.monotonic()
    with socket.create_connection(("127.0.0.1", f.port), 5) as sock:
        sock.sendall(
            f"POST /api/run?t=wrong HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{f.port}\r\n"
            f"Content-Length: 100\r\n\r\npartial".encode()
        )
        sock.shutdown(socket.SHUT_WR)
        head, _ = _recv_http_response(sock)
        assert head.startswith(b"HTTP/1.1 403")
        assert b"connection: close" in head.lower()
    assert time.monotonic() - t2 < 1.0

    # Client drops socket entirely mid-body
    sock = socket.create_connection(("127.0.0.1", f.port), 5)
    sock.sendall(
        f"POST /api/run?t=wrong HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{f.port}\r\n"
        f"Content-Length: 500\r\n\r\nabc".encode()
    )
    sock.close()

    # Server still healthy for valid requests
    status, _ = _post(f"http://127.0.0.1:{f.port}", "/api/run", b'{"command":"Version"}', token=f.token)
    assert status == 200
    assert FakeCommands.log == [("A1200", "Version")]


def test_fleet_close_shuts_down_server_socket_and_watch_threads(monkeypatch):
    before = set(threading.enumerate())
    f = make_fleet(monkeypatch, "A500", "A1200")
    f.start(0)
    port = f.port
    server_thread = f._server_thread
    watch_threads = list(f._watch_threads)
    assert server_thread is not None and server_thread.is_alive()
    assert len(watch_threads) == 2
    # Give _watch threads a moment to settle into stop.wait(...)
    time.sleep(0.05)

    f.close(timeout=5.0)
    assert f.httpd is None
    assert not server_thread.is_alive()
    assert all(not t.is_alive() for t in watch_threads)
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), 1)
    assert set(threading.enumerate()) <= before


def test_fleet_close_survives_failed_assertion(monkeypatch):
    before = set(threading.enumerate())
    f = make_fleet(monkeypatch, "A1200")
    f.start(0)
    port = f.port
    watch_threads = list(f._watch_threads)
    server_thread = f._server_thread

    def failing_probe():
        try:
            assert False, "simulated test assertion failure"
        finally:
            f.close(timeout=5.0)

    with pytest.raises(AssertionError, match="simulated test assertion failure"):
        failing_probe()

    assert f.httpd is None
    assert not server_thread.is_alive()
    assert all(not t.is_alive() for t in watch_threads)
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), 1)
    assert set(threading.enumerate()) <= before


def test_fleet_close_stops_threads_spawned_by_sync(private_config):
    from amigent import roster

    before = set(threading.enumerate())
    a = roster.remember("A", "192.0.2.1")
    f = fleet.Fleet(roster.load())
    f.start(0)
    b = roster.remember("B", "192.0.2.2")
    roster.edit(a["id"], address="192.0.2.3")
    f.sync()
    watch_threads = list(f._watch_threads)
    assert len(watch_threads) >= 2
    time.sleep(0.05)

    f.close(timeout=5.0)
    assert f.httpd is None
    assert all(not t.is_alive() for t in watch_threads)
    assert set(threading.enumerate()) <= before
    assert roster.address(b["id"]) == "192.0.2.2"
