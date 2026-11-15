"""TLSONLY closes remote plaintext, including when TLS is not listening.

The Amiga daemon is not executed. The C decision is compiled here from the
functions in amigentd.c and run on this machine. Loopback fakes cover the
client, and nothing dials an address that is not 127.0.0.1.
"""

import shutil
import socket
import struct
import subprocess
import threading
import time
from pathlib import Path

import pytest

from amigent.channel import (
    AUDIO,
    CMD_AUTH,
    CMD_CHANNEL,
    PLAIN_CLOSED,
    AmigaChannel,
    Commands,
    admission_failure,
    audio_uses_tls,
    connection_peer,
    plain_closed_message,
    plain_session_refused,
    tls_only_locks_plain,
)
from amigent.errors import AmigaError
from amigent.pack import Policy

ROOT = Path(__file__).resolve().parents[1]
DAEMON = ROOT / "src" / "native" / "amiga" / "daemon" / "amigentd.c"


def _hello(flags: int, protocol: int = 5) -> bytes:
    return b"AMGT" + struct.pack(">HH", protocol, flags)


def _serve(flags: int, handler):
    """A loopback listener. handler(conn) speaks after accept."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    def run():
        conn, _ = listener.accept()
        try:
            handler(conn)
        finally:
            try:
                conn.close()
            except OSError:
                pass
            listener.close()

    threading.Thread(target=run, daemon=True).start()
    return port


def _read_some(conn: socket.socket, timeout: float = 0.4) -> bytes:
    conn.settimeout(timeout)
    got = bytearray()
    try:
        while True:
            chunk = conn.recv(64)
            if not chunk:
                break
            got.extend(chunk)
            if len(got) >= 64:
                break
    except socket.timeout:
        pass
    return bytes(got)


def test_operational_rule_and_the_setup_exception():
    """TLS availability is a column of the matrix and does not open the port."""
    for listening in (True, False):
        assert tls_only_locks_plain(tls_only=True, tls_listening=listening, setup=False)
        assert not tls_only_locks_plain(tls_only=True, tls_listening=listening, setup=True)
        assert not tls_only_locks_plain(tls_only=False, tls_listening=listening, setup=False)
        assert not tls_only_locks_plain(tls_only=False, tls_listening=listening, setup=True)
    # A failed handshake is not an argument. The lock stays closed.
    assert tls_only_locks_plain(tls_only=True, tls_listening=True, setup=False)
    assert tls_only_locks_plain(tls_only=True, tls_listening=False, setup=False)


def test_remote_plaintext_is_refused_before_auth_and_loopback_is_not():
    assert plain_session_refused(PLAIN_CLOSED, "203.0.113.4", tls_socket=False, plain=True)
    assert plain_session_refused(PLAIN_CLOSED, "203.0.113.4", tls_socket=False, plain=False)
    assert not plain_session_refused(PLAIN_CLOSED, "203.0.113.4", tls_socket=True, plain=False)
    assert not plain_session_refused(PLAIN_CLOSED, "127.0.0.1", tls_socket=False, plain=True)
    assert plain_session_refused(PLAIN_CLOSED, "127.0.0.1", tls_socket=False, plain=False)
    assert not plain_session_refused(0, "203.0.113.4", tls_socket=False, plain=True)
    assert audio_uses_tls(PLAIN_CLOSED, "amiga.example")
    assert audio_uses_tls(PLAIN_CLOSED, "203.0.113.4")
    assert not audio_uses_tls(PLAIN_CLOSED, "127.0.0.1")
    assert not audio_uses_tls(PLAIN_CLOSED, "localhost")
    assert not audio_uses_tls(0, "203.0.113.4")


def test_daemon_source_closes_remote_plain_before_auth():
    text = DAEMON.read_text(encoding="latin-1")
    body = text.split("/* BEGIN PLAIN ADMISSION */", 1)[1].split("/* END PLAIN ADMISSION */", 1)[0]
    assert "tls_open" not in body
    assert "if (tls_only && !setup && !peer_is_loopback)" in body
    assert "locked = tls_only && tls_open" not in text
    close = text.split("if (amigent_plain_reject(tls_only, setup_mode,", 1)[1]
    close = close.split("pend[i].fd = fd;", 1)[0]
    assert "htonl(INADDR_LOOPBACK)" in close
    assert "close_fd(fd)" in close
    assert "recv(" not in close
    assert "CMD_AUTH" not in close
    pump = text.split("if (SSL_accept(ssl) != 1)", 1)[1].split("connect(", 1)[0]
    assert "return;" in pump
    assert "do not open the plain port" in pump
    assert text.count("setup_mode = TRUE") == 1
    assert "audio_only" not in text
    assert "plain connection is audio only" not in text
    # The audio fast path for an unlocked plain peer is unchanged.
    assert "BOOL plain = !peer_local(l);" in text
    assert "SetTaskPri(me, 5);" in text


def test_native_admission_harness(tmp_path):
    """The C decision, compiled and run. Same function the daemon calls."""
    if not shutil.which("gcc"):
        pytest.skip("no gcc")
    text = DAEMON.read_text(encoding="latin-1")
    body = text.split("/* BEGIN PLAIN ADMISSION */", 1)[1].split("/* END PLAIN ADMISSION */", 1)[0]
    src = tmp_path / "admit.c"
    src.write_text(body + "\n" + (ROOT / "tests" / "c" / "admit_harness.c").read_text(encoding="utf-8"),
                   encoding="utf-8")
    exe = tmp_path / "admit"
    done = subprocess.run(
        ["gcc", "-Wall", "-Wextra", "-Werror", "-std=c99", "-o", str(exe), str(src)],
        capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert run.stderr == ""


def test_external_plaintext_audio_and_auth_are_not_sent(monkeypatch):
    """A plain AUDIO connect to a TLSONLY daemon sends nothing after the hello."""
    seen = {}

    def handler(conn):
        conn.sendall(_hello(PLAIN_CLOSED | 1))
        seen["after"] = _read_some(conn)

    port = _serve(PLAIN_CLOSED | 1, handler)
    monkeypatch.setattr("amigent.channel.connection_peer", lambda sock: "203.0.113.9")
    with pytest.raises(AmigaError, match="only encrypted"):
        AmigaChannel("127.0.0.1", port, timeout=2, key="long-term-secret").connect(plain=True)
    deadline = time.monotonic() + 2
    while "after" not in seen and time.monotonic() < deadline:
        time.sleep(0.01)
    assert seen["after"] == b""
    assert CMD_AUTH == 17 and AUDIO == 38


def test_external_command_channel_is_refused_the_same_way(monkeypatch):
    seen = {}

    def handler(conn):
        conn.sendall(_hello(PLAIN_CLOSED))
        seen["after"] = _read_some(conn)

    port = _serve(PLAIN_CLOSED, handler)
    monkeypatch.setattr("amigent.channel.connection_peer", lambda sock: "203.0.113.9")
    with pytest.raises(AmigaError, match="only encrypted"):
        Commands("127.0.0.1", 1, port, timeout=2).connect()
    deadline = time.monotonic() + 2
    while "after" not in seen and time.monotonic() < deadline:
        time.sleep(0.01)
    assert seen["after"] == b""
    assert CMD_CHANNEL == 20


def test_loopback_plain_still_opens_a_channel():
    """127.0.0.1 with flag 4 is the pump's socket, and a plain channel still completes."""

    def handler(conn):
        conn.sendall(_hello(PLAIN_CLOSED))
        cmd = conn.recv(10)
        assert cmd[0] == CMD_CHANNEL
        conn.sendall(b"\0")

    port = _serve(PLAIN_CLOSED, handler)
    channel = AmigaChannel("127.0.0.1", port, timeout=2, key="")
    channel.policy = Policy("loopback", "127.0.0.1", mode="off")
    channel.policy.rates = {"deflate_fast": 1}
    channel.connect(plain=True)
    assert channel._sock is not None
    assert connection_peer(channel._sock) == "127.0.0.1"
    channel.close()


def test_without_tlsonly_plain_audio_still_connects():
    pcm = b"\x01\x00\x02\x00"

    def handler(conn):
        conn.sendall(_hello(0))
        assert conn.recv(10)[0] == CMD_CHANNEL
        conn.sendall(b"\0")
        start = conn.recv(10)
        assert start[0] == AUDIO and start[1] == 1
        conn.sendall(b"\0")
        conn.sendall(struct.pack(">II", 48000, len(pcm)) + pcm)
        conn.sendall(struct.pack(">II", 48000, 0xFFFFFFFF))

    port = _serve(0, handler)
    channel = AmigaChannel("127.0.0.1", port, timeout=2, key="")
    channel.policy = Policy("plain-audio", "127.0.0.1", mode="off")
    channel.policy.rates = {"deflate_fast": 1}
    channel.connect(plain=True)
    channel.audio_start()
    assert channel.audio_read() == (48000, pcm)
    assert channel.audio_read() is None
    channel.close()


def test_viewer_uses_tls_for_remote_audio_when_the_plain_port_is_closed():
    media = (ROOT / "src" / "amigent" / "viewer.py").read_text(encoding="utf-8")
    body = media.split("def _media", 1)[1].split("def _read_screens", 1)[0]
    assert "connect_audio(tls=audio_uses_tls(self.screen.flags, self.host))" in body
    assert "plain=True" not in body


def test_tls_audio_stream_keeps_the_framing(tmp_path, monkeypatch):
    import ssl

    from amigent import tls

    monkeypatch.setattr(tls, "FOLDER", tmp_path)
    made = tls.make_certificate("127.0.0.1")
    if made is None:
        pytest.skip("no openssl")
    for_amiga, certificate = made
    (tmp_path / "server.pem").write_bytes(for_amiga)
    tls.remember("127.0.0.1", certificate)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(tmp_path / "server.pem")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    tls_port = listener.getsockname()[1]
    pcm = b"\x10\x00\x20\x00"
    seen = {}

    def run():
        conn, _ = listener.accept()
        try:
            with context.wrap_socket(conn, server_side=True) as secure:
                secure.sendall(_hello(PLAIN_CLOSED))
                seen["channel"] = secure.recv(10)
                secure.sendall(b"\0")
                seen["audio"] = secure.recv(10)
                secure.sendall(b"\0")
                secure.sendall(struct.pack(">II", 48000, len(pcm)) + pcm)
                secure.sendall(struct.pack(">II", 48000, 0xFFFFFFFF))
        except (OSError, ssl.SSLError):
            seen["error"] = True
        finally:
            listener.close()

    threading.Thread(target=run, daemon=True).start()
    # connect_audio(tls=True) is this call: AmigaChannel.connect with a pinned cert.
    channel = AmigaChannel("127.0.0.1", tls_port - 1, timeout=5, key="")
    channel.policy = Policy("tls-audio", "127.0.0.1", mode="off", path=tmp_path / "p.json")
    channel.policy.rates = {"deflate_fast": 1}
    channel.connect()
    assert hasattr(channel._sock, "version")
    channel.audio_start()
    assert channel.audio_read() == (48000, pcm)
    assert channel.audio_read() is None
    channel.close()
    assert seen.get("channel", b"")[:1] == bytes([CMD_CHANNEL])
    assert seen.get("audio", b"")[:2] == bytes([AUDIO, 1])
    assert "error" not in seen


def test_tls_failure_does_not_open_plaintext(monkeypatch):
    import ssl

    from amigent import tls

    plain = []
    monkeypatch.setattr(tls, "wanted", lambda host: True)

    def fail(host, port, timeout):
        raise ssl.SSLError("handshake failed")

    real_plain = AmigaChannel._open_plain

    def open_plain(self):
        plain.append(self.port)
        return real_plain(self)

    monkeypatch.setattr(tls, "connect", fail)
    monkeypatch.setattr(AmigaChannel, "_open_plain", open_plain)
    link = Commands("127.0.0.1", 1, 6801, timeout=2)
    with pytest.raises(AmigaError, match="cannot reach"):
        link.connect_audio(tls=True)
    assert plain == []
    assert link.backend is None or not link.connected


def _wait_key(seen: dict) -> None:
    deadline = time.monotonic() + 2
    while "after" not in seen and time.monotonic() < deadline:
        time.sleep(0.01)


def test_tls_unavailable_refuses_audio_and_channel_before_the_key(monkeypatch):
    """Flag 4 without flag 2: TLS is not up, and neither command is sent."""
    seen = {}

    def handler(conn):
        conn.sendall(_hello(PLAIN_CLOSED | 1))
        seen["after"] = _read_some(conn)

    port = _serve(PLAIN_CLOSED | 1, handler)
    monkeypatch.setattr("amigent.channel.connection_peer", lambda sock: "203.0.113.9")
    with pytest.raises(AmigaError, match="TLS port is not available"):
        AmigaChannel("127.0.0.1", port, timeout=2, key="long-term-secret").connect(plain=True)
    _wait_key(seen)
    assert seen["after"] == b""
    assert "long-term-secret" not in seen["after"].decode("latin-1", "replace")

    seen.clear()

    def channel_handler(conn):
        conn.sendall(_hello(PLAIN_CLOSED))
        seen["after"] = _read_some(conn)

    port = _serve(PLAIN_CLOSED, channel_handler)
    with pytest.raises(AmigaError, match="TLS port is not available"):
        Commands("127.0.0.1", 1, port, timeout=2).connect()
    _wait_key(seen)
    assert seen["after"] == b""
    from amigent import tls
    assert admission_failure(tls.TLS_UNAVAILABLE_TEXT)
    assert admission_failure(tls.TLS_HANDSHAKE_TEXT)
    assert not admission_failure("cannot reach amigentd at 127.0.0.1:6801")


def test_tls_listening_still_refuses_remote_plaintext(monkeypatch):
    """Flag 2 and flag 4: TLS is up, the certificate text is used, no key goes out."""
    seen = {}

    def handler(conn):
        conn.sendall(_hello(PLAIN_CLOSED | 2 | 1))
        seen["after"] = _read_some(conn)

    port = _serve(PLAIN_CLOSED | 2 | 1, handler)
    monkeypatch.setattr("amigent.channel.connection_peer", lambda sock: "203.0.113.9")
    with pytest.raises(AmigaError, match="certificate"):
        Commands("127.0.0.1", 1, port, timeout=2).connect_audio(tls=False)
    _wait_key(seen)
    assert seen["after"] == b""
    assert plain_closed_message(PLAIN_CLOSED | 2).startswith("amigentd takes only encrypted")
    assert "TLS port is not available" in plain_closed_message(PLAIN_CLOSED)


def test_explicit_setup_admits_audio_and_the_command_channel(tmp_path):
    """SETUP does not set flag 4, so the installer can still speak plaintext."""
    def audio_handler(conn):
        conn.sendall(_hello(0))
        assert conn.recv(10)[0] == CMD_CHANNEL
        conn.sendall(b"\0")
        start = conn.recv(10)
        assert start[0] == AUDIO and start[1] == 1
        conn.sendall(b"\0")
        conn.sendall(struct.pack(">II", 48000, 0xFFFFFFFF))

    port = _serve(0, audio_handler)
    channel = AmigaChannel("127.0.0.1", port, timeout=2, key="")
    channel.policy = Policy("setup-audio", "127.0.0.1", mode="off", path=tmp_path / "p.json")
    channel.policy.rates = {"deflate_fast": 1}
    channel.connect(plain=True)
    channel.audio_start()
    assert channel.audio_read() is None
    channel.close()

    def command_handler(conn):
        conn.sendall(_hello(0, protocol=4))
        assert conn.recv(10)[0] == CMD_CHANNEL
        conn.sendall(b"\0")

    port = _serve(0, command_handler)
    link = Commands("127.0.0.1", 1, port, timeout=2)
    link.connect(plain=True)
    assert link.connected
    link.close()


def test_screen_client_does_not_send_the_key(monkeypatch):
    from amigent.amigentd import Amigentd, AmigentdError

    seen = {}

    def handler(conn):
        conn.sendall(_hello(PLAIN_CLOSED | 1))
        seen["after"] = _read_some(conn)

    port = _serve(PLAIN_CLOSED | 1, handler)
    monkeypatch.setattr("amigent.channel.connection_peer", lambda sock: "203.0.113.9")
    with pytest.raises(AmigentdError, match="TLS port is not available"):
        Amigentd("127.0.0.1", port, timeout=2, key="long-term-secret").connect()
    _wait_key(seen)
    assert seen["after"] == b""


def test_command_connect_does_not_fall_back_to_amigactld(monkeypatch):
    from amigent.amigactl import AmigaCtl

    def handler(conn):
        conn.sendall(_hello(PLAIN_CLOSED))
        _read_some(conn)

    port = _serve(PLAIN_CLOSED, handler)
    monkeypatch.setattr("amigent.channel.connection_peer", lambda sock: "203.0.113.9")

    def boom(self):
        raise AssertionError("amigactld")

    monkeypatch.setattr(AmigaCtl, "connect", boom)
    with pytest.raises(AmigaError, match="TLS port is not available"):
        Commands("127.0.0.1", 1, port, timeout=2).connect()


def test_handshake_failure_does_not_read_the_plain_port(monkeypatch):
    from amigent import tls

    plain = []
    monkeypatch.setattr(tls, "wanted", lambda host: True)

    def dial(address, host, port, timeout):
        raise tls.TlsHandshakeFailed(tls.TLS_HANDSHAKE_TEXT)

    def peek(address, port, timeout):
        plain.append(port)
        return True

    monkeypatch.setattr(tls, "_dial", dial)
    monkeypatch.setattr(tls, "_plain_requires_tls", peek)
    with pytest.raises(tls.TlsHandshakeFailed, match="not retried in the clear"):
        tls.connect("127.0.0.1", 6801, 2)
    assert plain == []


def test_tls_port_down_reads_the_hello_and_sends_nothing(monkeypatch):
    from amigent import tls

    seen = {}

    def handler(conn):
        conn.sendall(_hello(PLAIN_CLOSED | 1))
        seen["after"] = _read_some(conn)

    port = _serve(PLAIN_CLOSED | 1, handler)
    monkeypatch.setattr(tls, "wanted", lambda host: True)
    with pytest.raises(tls.TlsUnavailable, match="TLS port is not available"):
        tls.connect("127.0.0.1", port, 2)
    _wait_key(seen)
    assert seen["after"] == b""


def test_viewer_surfaces_the_tls_failure():
    from amigent import tls
    from amigent.viewer import Viewer

    reasons = []
    viewer = Viewer.__new__(Viewer)
    viewer.online = None
    viewer.offline_reason = ""
    viewer.event = lambda kind, **fields: reasons.append((kind, fields))
    viewer._set_online(False, tls.TLS_UNAVAILABLE_TEXT)
    assert reasons == [("online", {"online": False, "reason": tls.TLS_UNAVAILABLE_TEXT})]
    viewer._set_online(False, tls.TLS_HANDSHAKE_TEXT)
    assert reasons[-1][1]["reason"] == tls.TLS_HANDSHAKE_TEXT
    page = (ROOT / "src" / "amigent" / "web" / "viewer.js").read_text(encoding="utf-8")
    english = (ROOT / "src" / "amigent" / "web" / "locales" / "en.json").read_text(encoding="utf-8")
    assert "tls_unavailable" in page and "tls_unavailable" in english
    assert "TLS port is not available" in page
    assert "not retried in the clear" in page
