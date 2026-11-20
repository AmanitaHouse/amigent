"""Viewer playback and amiga_listen. Nothing here contacts an Amiga or plays a sample.

The protected daemon's bytes stay the ones already packaged. A passing test
means the PC accepted framed audio, not that the mix was heard on hardware.
"""

import hashlib
import struct

import pytest

import amigent.server as server
from amigent.channel import (
    PLAIN_CLOSED, PLAIN_CLOSED_TEXT, AmigaChannel, Commands, audio_uses_tls, feature_opcode,
    pcm_wav,
)
from amigent.errors import AmigaError
from amigent.paths import AMIGA
from amigent.viewer import Viewer, pcm_message
from amigent.webserver import WEB

DAEMON = (131292, "1e0e3f65d46b62c93f7986d8137120ef5e2dec2515a9b63f6aa5909d2e75e9ca")


def test_audio_capability_follows_the_advertisement_and_the_protocol():
    assert feature_opcode(6, "AUDIO", {"audio": "1"}) == 48
    assert feature_opcode(6, "AUDIO", {}) is None
    assert feature_opcode(6, "AUDIO", {"audio": "0"}) is None
    assert feature_opcode(5, "AUDIO", {"audio": "1"}) == 38
    assert feature_opcode(5, "AUDIO", {}) is None
    assert feature_opcode(4, "AUDIO", {"audio": "1"}) is None
    viewer = (WEB.parent / "viewer.py").read_text(encoding="utf-8")
    page = (WEB / "viewer.js").read_text(encoding="utf-8")
    # The fork keeps the SAGA picture-in-picture beside the on-demand audio.
    assert "_poll_pip" in viewer and "drawPip" in page and "kind === 4" in page


def test_remote_tlsonly_audio_does_not_accept_plaintext(monkeypatch):
    assert audio_uses_tls(PLAIN_CLOSED, "192.0.2.10")
    assert not audio_uses_tls(PLAIN_CLOSED, "127.0.0.1")
    assert not audio_uses_tls(PLAIN_CLOSED, "localhost")
    assert not audio_uses_tls(PLAIN_CLOSED, "::1")
    assert not audio_uses_tls(0, "192.0.2.10")

    class Plain:
        closed = False

        def close(self):
            self.closed = True

    class Encrypted(Plain):
        def version(self):
            return "TLSv1.3"

    made = []

    class FakeChannel:
        def __init__(self, host, port, timeout):
            self.host, self.port, self.timeout = host, port, timeout
            self._sock = Encrypted() if host == "tls" else Plain()
            self.closed = False
            made.append(self)

        def connect(self):
            if self.host == "down":
                raise AmigaError(PLAIN_CLOSED_TEXT)

        def close(self):
            self.closed = True
            self._sock.close()

    monkeypatch.setattr("amigent.channel.AmigaChannel", FakeChannel)
    monkeypatch.setattr("amigent.channel.AmigaCtl", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("audio fell through to amigactld")))

    refused = Commands("192.0.2.10")
    with pytest.raises(AmigaError, match="only encrypted"):
        refused.connect_audio(tls=True)
    assert refused.backend is None and made[-1].closed

    failed = Commands("down")
    with pytest.raises(AmigaError, match="only encrypted"):
        failed.connect_audio(tls=True)
    assert failed.backend is None

    accepted = Commands("tls")
    accepted.connect_audio(tls=True)
    assert accepted.backend is made[-1] and accepted.is_tls


class Link:
    def __init__(self):
        self.connected = False
        self.tls = None
        self.started = 0
        self.stopped = 0
        self.closed = 0
        self.reads = []

    def connect_audio(self, *, tls):
        self.tls = tls
        self.connected = True

    def audio_start(self):
        self.started += 1

    def audio_read(self):
        if not self.reads:
            return None
        item = self.reads.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def audio_stop(self):
        self.stopped += 1

    def close(self):
        self.closed += 1
        self.connected = False


def _page(host="192.0.2.10", flags=0):
    viewer = Viewer(host, screen_port=1, ctl_port=1)
    viewer.screen.flags = flags
    viewer.clients.add(object())
    viewer.sent = []
    viewer.broadcast = lambda data: viewer.sent.append(data)
    viewer.event = lambda kind, **fields: viewer.sent.append((kind, fields))
    return viewer


def test_playback_starts_only_when_asked_and_stops_cleanly():
    viewer = _page(flags=PLAIN_CLOSED)
    viewer.amiga = {"audio": "1"}
    assert not viewer._hearing()
    viewer.submit({"t": "audio", "on": True})
    assert viewer._hearing() and viewer._audio_ready()
    link = Link()
    link.reads = [(48000, b"\x01\x00\x02\x00"), None]
    viewer._play_audio(link)
    assert link.tls is True and link.started == 1 and link.stopped == 0
    assert viewer.sent[0] == ("audio", {"on": True})
    frame = viewer.sent[1]
    assert frame == pcm_message(48000, b"\x01\x00\x02\x00")
    assert frame[0] == 5 and struct.unpack(">I", frame[1:5]) == (48000,)

    viewer.submit({"t": "audio", "on": False})
    link.reads = [(48000, b"\x00\x00\x00\x00")]
    viewer._play_audio(link)
    assert link.stopped == 1 and link.closed == 1
    assert ("audio", {"on": False}) in viewer.sent


def test_unsupported_audio_and_a_lost_connection_leave_no_stream():
    viewer = _page()
    viewer.amiga = {}
    viewer.submit({"t": "audio", "on": True})
    assert viewer._hearing() and not viewer._audio_ready()
    viewer.amiga = {"os": "AmigaOS", "audio": ""}
    assert not viewer._audio_ready() and not viewer.hear
    assert ("audio", {"on": False}) in viewer.sent

    viewer.amiga = {"audio": "1"}
    viewer.submit({"t": "audio", "on": True})
    link = Link()
    link.reads = [AmigaError("the Amiga does not answer")]
    with pytest.raises(AmigaError):
        viewer._play_audio(link)
    viewer._drop_audio(link)
    assert not viewer.hear and link.closed == 1

    odd = Link()
    viewer.hear = True
    odd.reads = [(48000, b"\x00\x00\x00")]
    with pytest.raises(AmigaError, match="stereo"):
        viewer._play_audio(odd)


def test_reconnection_does_not_keep_playback():
    viewer = _page()
    viewer.amiga = {"audio": "1"}
    viewer.submit({"t": "audio", "on": True})
    viewer._set_online(False, "the Amiga does not answer")
    assert viewer.hear is False
    viewer._set_online(True)
    assert viewer.hear is False and not viewer._hearing()
    client = next(iter(viewer.clients))
    viewer.hear = True
    viewer.leave(client)
    assert viewer.hear is False and not viewer.clients


def test_the_page_arms_playback_from_the_button_and_keeps_the_screen_path():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    js = (WEB / "viewer.js").read_text(encoding="utf-8")
    assert 'id="hear"' in html and 'id="screen"' in html
    assert 'send({ t: "audio", on: true })' in js
    assert 'send({ t: "audio", on: false })' in js
    assert "amigent-pcm" in js and "kind === 5" in js
    assert "function drawTiles" in js and "function onBinary" in js
    connect = js.split("function connect()", 1)[1].split("function showState()", 1)[0]
    assert "audio" not in connect


def test_listen_validates_and_reports_transport_results(monkeypatch):
    for bad in (True, "1", None, 0, 0.1, 3):
        with pytest.raises(AmigaError, match="0.2 to 2"):
            server._listen_seconds(bad)
    assert server._listen_seconds(0.2) == 0.2
    assert server._listen_seconds(2) == 2

    class Quiet:
        def sysinfo(self):
            return {"audio": "0"}

        def audio(self, ms):
            raise AssertionError("the mix was read")

    monkeypatch.setattr(server, "ctl", Quiet())
    monkeypatch.setattr(server, "_with_ctl", lambda fn: fn())
    assert server.amiga_listen(1) == ["this Amiga has no AHI mix to hear"]

    class Down:
        def sysinfo(self):
            return {"audio": "1"}

        def audio(self, ms):
            raise AmigaError("the Amiga does not answer")

    monkeypatch.setattr(server, "ctl", Down())
    with pytest.raises(AmigaError, match="does not answer"):
        server.amiga_listen(1)

    pcm = b"\x00\x00" * int(0.2 * 48000 * 2)

    class Playing:
        def sysinfo(self):
            return {"audio": "1"}

        def audio(self, ms):
            assert ms == 200
            return 48000, pcm

    monkeypatch.setattr(server, "ctl", Playing())
    text, block = server.amiga_listen(0.2)
    assert text == f"heard {len(pcm)} bytes at 48000 Hz"
    assert block.data == pcm_wav(pcm, 48000) and block.data.startswith(b"RIFF")

    clock = {"t": 0.0}
    monkeypatch.setattr(server.time, "monotonic", lambda: clock.__setitem__("t", clock["t"] + 1) or clock["t"])
    monkeypatch.setattr(server.time, "sleep", lambda _seconds: None)

    class Silent:
        def sysinfo(self):
            return {"audio": "1"}

        def audio(self, ms):
            return 48000, b""

    monkeypatch.setattr(server, "ctl", Silent())
    assert server.amiga_listen(1) == ["nothing is playing through AHI"]


def test_the_protected_daemon_is_unchanged():
    data = (AMIGA / "bin" / "amigentd.apollo").read_bytes()
    assert len(data) == DAEMON[0]
    assert hashlib.sha256(data).hexdigest() == DAEMON[1]
