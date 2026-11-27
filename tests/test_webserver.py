import http.client
import json
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest

from amigent import webserver


class FakeManager:
    def __init__(self):
        self.calls = []
        self.url = "http://127.0.0.1:6820/?t=mgr"

    def status(self):
        return [{"id": "1", "name": "A1200", "host": "10.0.0.1"}]

    def manage(self, body):
        self.calls.append(("manage", body))
        return {"machines": self.status()}

    def connect(self, target):
        self.calls.append(("connect", target))
        return f"http://127.0.0.1:6811/?t=next&target={target}"


class FakeViewer:
    def __init__(self):
        self.token = "valid-viewer-token"
        self.host = "1"
        self.clients = set()
        self.clients_lock = threading.Lock()
        self.manager = FakeManager()
        self.clipboard = "hello"
        self.actions = []

    def machine_manager(self):
        return self.manager

    def set_address(self, address):
        self.actions.append(("address", address))
        return "http://127.0.0.1:6812/?t=addr"

    def update_action(self, action):
        self.actions.append(("update", action))
        return {"action": action}

    def read_clipboard(self):
        return self.clipboard

    def write_clipboard(self, text):
        self.actions.append(("clipboard", text))
        self.clipboard = text

    def queue_upload(self, folder, name, data, overwrite):
        self.actions.append(("upload", folder, name, len(data), overwrite))
        return {"queued": name, "size": len(data)}


@pytest.fixture
def viewer_server():
    viewer = FakeViewer()
    handler = type("TestHandler", (webserver._Handler,), {"viewer": viewer})
    httpd = webserver.QuietServer(("127.0.0.1", 0), handler)
    viewer.port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield viewer, f"http://127.0.0.1:{viewer.port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5.0)


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


def _request(url: str, *, method: str = "GET", data: bytes | None = None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_shared_webserver_static_get_and_valid_posts(viewer_server):
    viewer, base = viewer_server

    # Static assets and locale JSON work without a token
    st, js = _request(f"{base}/ui.js")
    assert st == 200 and len(js) > 0
    st, loc = _request(f"{base}/locales/en.json")
    assert st == 200 and json.loads(loc)

    # Normal GET operations
    assert _request(f"{base}/?t={viewer.token}")[0] == 200
    assert _request(f"{base}/?t=wrong")[0] == 403
    assert json.loads(_request(f"{base}/api/clients?t={viewer.token}")[1]) == {"clients": 0}
    assert json.loads(_request(f"{base}/api/clipboard?t={viewer.token}")[1]) == {"text": "hello"}

    # Successful POST operations
    st, body = _request(f"{base}/api/clipboard?t={viewer.token}", method="POST", data=b"amiga")
    assert st == 200 and json.loads(body) == {}
    st, body = _request(f"{base}/api/machines?t={viewer.token}", method="POST",
                        data=json.dumps({"id": "1", "action": "rename", "name": "New"}).encode())
    assert st == 200 and "machines" in json.loads(body)
    st, body = _request(f"{base}/api/connect?t={viewer.token}", method="POST",
                        data=json.dumps({"target": "10.0.0.2"}).encode())
    assert st == 200 and "10.0.0.2" in json.loads(body)["url"]
    st, body = _request(f"{base}/api/address?t={viewer.token}", method="POST", data=b"10.0.0.3")
    assert st == 200 and "url" in json.loads(body)
    st, body = _request(f"{base}/api/update?t={viewer.token}", method="POST", data=b"check")
    assert st == 200 and json.loads(body) == {"action": "check"}
    st, body = _request(f"{base}/api/upload?t={viewer.token}&folder=RAM:&name=test.txt",
                        method="POST", data=b"payload")
    assert st == 200 and json.loads(body) == {"queued": "test.txt", "size": 7}


def test_shared_webserver_early_403_drains_bounded_body_and_preserves_stream(viewer_server):
    viewer, base = viewer_server

    conn = http.client.HTTPConnection("127.0.0.1", viewer.port, timeout=10)
    try:
        # Wrong token with JSON body -> 403, body consumed
        conn.request("POST", "/api/machines?t=wrong", body=b'{"id":"1","action":"remove"}')
        r1 = conn.getresponse()
        assert r1.status == 403 and r1.read() == b"forbidden"

        # Unknown path with valid token -> 403, body consumed
        conn.request("POST", f"/api/not-allowed?t={viewer.token}", body=b'{"x":1}')
        r2 = conn.getresponse()
        assert r2.status == 403 and r2.read() == b"forbidden"

        # Same persistent connection stays aligned for a valid request
        conn.request("POST", f"/api/clipboard?t={viewer.token}", body=b"clean")
        r3 = conn.getresponse()
        assert r3.status == 200 and json.loads(r3.read()) == {}
    finally:
        conn.close()

    assert viewer.manager.calls == []
    assert viewer.actions == [("clipboard", "clean")]

    # Wrong token near MAX_MESSAGE (1 MiB) drains cleanly
    big_valid_for_drain = b"a" * webserver.MAX_MESSAGE
    st, _ = _request(f"{base}/api/clipboard?t=wrong", method="POST", data=big_valid_for_drain)
    assert st == 403
    assert viewer.actions == [("clipboard", "clean")]


def test_shared_webserver_rejects_oversized_malformed_and_stalled_posts(viewer_server, monkeypatch):
    viewer, _ = viewer_server
    monkeypatch.setattr(webserver, "DRAIN_TIMEOUT", 0.15)

    # Unauthenticated upload above MAX_MESSAGE MUST NOT drain up to MAX_UPLOAD (512 MiB)
    t0 = time.monotonic()
    with socket.create_connection(("127.0.0.1", viewer.port), 5) as sock:
        sock.sendall(
            f"POST /api/upload?t=wrong HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{viewer.port}\r\n"
            f"Content-Length: {webserver.MAX_MESSAGE + 1}\r\n\r\n".encode()
        )
        head, body = _recv_http_response(sock)
        assert head.startswith(b"HTTP/1.1 403")
        assert b"connection: close" in head.lower()
        assert body == b"forbidden"
    assert time.monotonic() - t0 < 1.0

    # Valid token above MAX_MESSAGE on /api/clipboard and above MAX_UPLOAD on /api/upload -> 413
    for path, limit in (("/api/clipboard", webserver.MAX_MESSAGE),
                        ("/api/upload", webserver.MAX_UPLOAD)):
        with socket.create_connection(("127.0.0.1", viewer.port), 5) as sock:
            sock.sendall(
                f"POST {path}?t={viewer.token} HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{viewer.port}\r\n"
                f"Content-Length: {limit + 1}\r\n\r\n".encode()
            )
            head, body = _recv_http_response(sock)
            assert head.startswith(b"HTTP/1.1 413")
            assert b"connection: close" in head.lower()
            assert json.loads(body) == {"error": "file too large"}

    # Malformed Content-Length and chunked Transfer-Encoding -> 400 (valid token) / 403 (bad token)
    for hdr in ("Content-Length: -1\r\n", "Content-Length: nope\r\n", "Transfer-Encoding: chunked\r\n"):
        with socket.create_connection(("127.0.0.1", viewer.port), 5) as sock:
            sock.sendall(
                f"POST /api/clipboard?t={viewer.token} HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{viewer.port}\r\n{hdr}\r\n".encode()
            )
            head, body = _recv_http_response(sock)
            assert head.startswith(b"HTTP/1.1 400")
            assert b"connection: close" in head.lower()
            assert json.loads(body) == {"error": "length missing"}

        with socket.create_connection(("127.0.0.1", viewer.port), 5) as sock:
            sock.sendall(
                f"POST /api/clipboard?t=wrong HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{viewer.port}\r\n{hdr}\r\n".encode()
            )
            head, _ = _recv_http_response(sock)
            assert head.startswith(b"HTTP/1.1 403")
            assert b"connection: close" in head.lower()

    # Stalled wrong-token POST times out boundedly
    t1 = time.monotonic()
    with socket.create_connection(("127.0.0.1", viewer.port), 5) as sock:
        sock.sendall(
            f"POST /api/clipboard?t=wrong HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{viewer.port}\r\n"
            f"Content-Length: 512\r\n\r\nhalf".encode()
        )
        head, _ = _recv_http_response(sock)
        assert head.startswith(b"HTTP/1.1 403")
        assert b"connection: close" in head.lower()
    assert time.monotonic() - t1 < 1.5

    # Stalled valid-token POST -> 400 incomplete body
    t2 = time.monotonic()
    with socket.create_connection(("127.0.0.1", viewer.port), 5) as sock:
        sock.sendall(
            f"POST /api/clipboard?t={viewer.token} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{viewer.port}\r\n"
            f"Content-Length: 512\r\n\r\nhalf".encode()
        )
        head, body = _recv_http_response(sock)
        assert head.startswith(b"HTTP/1.1 400")
        assert b"connection: close" in head.lower()
        assert json.loads(body) == {"error": "incomplete body"}
    assert time.monotonic() - t2 < 1.5

    # Client disconnects mid-body (write half closed) -> prompt 403 / 400 without waiting for timeout
    t3 = time.monotonic()
    with socket.create_connection(("127.0.0.1", viewer.port), 5) as sock:
        sock.sendall(
            f"POST /api/clipboard?t=wrong HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{viewer.port}\r\n"
            f"Content-Length: 200\r\n\r\nhalf".encode()
        )
        sock.shutdown(socket.SHUT_WR)
        head, _ = _recv_http_response(sock)
        assert head.startswith(b"HTTP/1.1 403")
        assert b"connection: close" in head.lower()
    assert time.monotonic() - t3 < 1.0

    assert viewer.actions == []
    assert viewer.manager.calls == []
