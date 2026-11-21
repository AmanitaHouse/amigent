"""Offline stock Viewer Hear lifecycle checks (not hardware evidence)."""
from __future__ import annotations

import struct

import pytest

from amigent.channel import PLAIN_CLOSED
from amigent.errors import AmigaError
from amigent.viewer import Viewer, pcm_message


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


def _page():
    viewer = Viewer("192.0.2.10", screen_port=1, ctl_port=1)
    viewer.screen.flags = PLAIN_CLOSED
    viewer.clients.add(object())
    viewer.sent = []
    viewer.broadcast = lambda data: viewer.sent.append(data)
    viewer.event = lambda kind, **fields: viewer.sent.append((kind, fields))
    viewer.amiga = {"audio": "1"}
    return viewer


def test_hear_off_stops_and_releases():
    viewer = _page()
    viewer.submit({"t": "audio", "on": True})
    link = Link()
    # First chunk then keep reading until Hear OFF flips mid-loop via submit below.
    # Drive one chunk, then turn off before next read returns.
    link.reads = [(48000, b"\x01\x00\x02\x00")]

    def between():
        viewer.submit({"t": "audio", "on": False})
        link.reads.append((48000, b"\x03\x00\x04\x00"))

    viewer._play_audio(link, between)
    assert link.started == 1 and link.stopped == 1 and link.closed == 1
    assert ("audio", {"on": False}) in viewer.sent
    assert not viewer.hear


def test_daemon_end_marker_while_hearing_returns_without_stop():
    """Current stock behaviour: end marker with Hear still on skips release."""
    viewer = _page()
    viewer.submit({"t": "audio", "on": True})
    link = Link()
    link.reads = [(48000, b"\x01\x00\x02\x00"), None]
    viewer._play_audio(link)
    assert viewer.hear is True
    assert link.started == 1 and link.stopped == 0 and link.closed == 0


def test_media_like_loop_restarts_after_daemon_end():
    """Simulates _media calling _play_audio again while Hear remains on."""
    viewer = _page()
    viewer.submit({"t": "audio", "on": True})
    link = Link()
    link.reads = [(48000, b"\x01\x00\x02\x00"), None]
    viewer._play_audio(link)
    assert viewer._hearing()
    # Second entry as _media would do
    link.reads = [(48000, b"\x05\x00\x06\x00"), None]
    viewer._play_audio(link)
    assert link.started == 2  # silent restart — safety gap for HW UI sessions


def test_tls_or_amiga_error_drop_requires_user_reclick():
    viewer = _page()
    viewer.submit({"t": "audio", "on": True})
    link = Link()
    link.reads = [AmigaError("TLS handshake failed")]
    with pytest.raises(AmigaError):
        viewer._play_audio(link)
    viewer._drop_audio(link)
    assert viewer.hear is False and link.closed == 1
    assert not viewer._hearing()


def test_last_client_leave_clears_hear():
    viewer = _page()
    viewer.submit({"t": "audio", "on": True})
    client = next(iter(viewer.clients))
    viewer.leave(client)
    assert viewer.hear is False and not viewer._hearing()


def test_pcm_message_framing_unchanged():
    pcm = b"\x01\x00\x02\x00" * 4
    msg = pcm_message(47931, pcm)
    assert msg[0] == 5 and struct.unpack(">I", msg[1:5]) == (47931,) and msg[5:] == pcm
